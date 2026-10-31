"""End-to-End integration test for the MCP Gateway Streamable HTTP transport.

Verifies:
1. Hub connects to two independent downstream MCP servers (Server A & Server B).
2. MCP Client connects ONLY to the Hub's unified '/mcp' Streamable HTTP endpoint.
3. Client dynamically discovers tools from both servers with collision-free namespacing.
4. Client successfully invokes tools from Server A and Server B, receiving native responses.
5. Duplicate tool names across servers ('calculate') route independently and correctly.
6. Dynamic updates (disabling/re-enabling/refreshing downstream servers) update tools dynamically.
7. Execution audit logs record tool invocations made through the gateway.
"""

import asyncio
import socket
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.main import app

DEMO_SERVER_A = str(Path(__file__).resolve().parent.parent.parent / "demo_server" / "server.py")
DEMO_SERVER_B = str(Path(__file__).resolve().parent.parent.parent / "demo_server" / "server_b.py")


def find_free_port() -> int:
    """Allocate an available local TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
async def running_hub_server() -> AsyncGenerator[tuple[str, int], None]:
    """Start uvicorn server running MCP Hub in background task for real HTTP & SSE tests."""
    port = find_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    server_task = asyncio.create_task(server.serve())

    # Wait until uvicorn starts
    while not server.started:
        await asyncio.sleep(0.05)

    base_url = f"http://127.0.0.1:{port}"
    try:
        yield base_url, port
    finally:
        server.should_exit = True
        await server_task


@pytest.mark.asyncio
async def test_mcp_gateway_e2e_two_servers_and_dynamic_lifecycle(
    running_hub_server: tuple[str, int],
):
    base_url, port = running_hub_server
    gateway_mcp_url = f"{base_url}/mcp"

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as rest_client:
        # 1. Register Downstream Server A (math_server)
        resp_a = await rest_client.post(
            "/api/v1/servers",
            json={
                "name": "math_server",
                "description": "Demo Math Server with calculate & echo",
                "transport": "stdio",
                "stdio_config": {
                    "command": sys.executable,
                    "args": [DEMO_SERVER_A],
                },
                "enabled": True,
            },
        )
        assert resp_a.status_code == 201, resp_a.text
        server_a_id = resp_a.json()["id"]

        # 2. Register Downstream Server B (text_server)
        resp_b = await rest_client.post(
            "/api/v1/servers",
            json={
                "name": "text_server",
                "description": "Demo Text Server with duplicate calculate & transform",
                "transport": "stdio",
                "stdio_config": {
                    "command": sys.executable,
                    "args": [DEMO_SERVER_B],
                },
                "enabled": True,
            },
        )
        assert resp_b.status_code == 201, resp_b.text
        server_b_id = resp_b.json()["id"]

        # 3. Connect both downstream servers
        connect_a = await rest_client.post(f"/api/v1/servers/{server_a_id}/connect")
        assert connect_a.status_code == 200, connect_a.text
        assert connect_a.json()["health_status"] == "HEALTHY"

        connect_b = await rest_client.post(f"/api/v1/servers/{server_b_id}/connect")
        assert connect_b.status_code == 200, connect_b.text
        assert connect_b.json()["health_status"] == "HEALTHY"

        # 4. Connect MCP Client ONLY to the Hub's /mcp Streamable HTTP endpoint
        # Upstream client does NOT know downstream addresses or transport configurations!
        async with (
            streamable_http_client(gateway_mcp_url) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            init_res = await session.initialize()
            assert init_res.server_info.name == "mcp-hub-gateway"
            assert init_res.capabilities.tools is not None
            assert init_res.capabilities.tools.list_changed is True

            # 5. Discover tools from unified gateway
            tools_res = await session.list_tools()
            tool_names = [t.name for t in tools_res.tools]
            tool_map = {t.name: t for t in tools_res.tools}

            # Verify tools from Server A are present and namespaced
            assert "math_server__calculate" in tool_names
            assert "math_server__echo" in tool_names
            assert "math_server__system_ping" in tool_names

            # Verify tools from Server B are present and namespaced
            assert "text_server__calculate" in tool_names
            assert "text_server__text_transform" in tool_names
            assert "text_server__json_prettify" in tool_names

            # Verify input schemas and descriptions preserved
            math_calc = tool_map["math_server__calculate"]
            assert math_calc.description is not None
            assert "expression" in math_calc.input_schema.get("properties", {})

            text_trans = tool_map["text_server__text_transform"]
            assert "mode" in text_trans.input_schema.get("properties", {})

            # 6. Execute tool on Server A: 'calculate' -> expression '25 * 4 + 10' = '110'
            call_a = await session.call_tool(
                "math_server__calculate",
                arguments={"expression": "25 * 4 + 10"},
            )
            assert call_a.is_error is False
            assert len(call_a.content) > 0
            assert call_a.content[0].text == "110"

            # 7. Execute duplicate-named tool on Server B: 'calculate' -> returns Server B format
            call_b = await session.call_tool(
                "text_server__calculate",
                arguments={"expression": "25 * 4 + 10"},
            )
            assert call_b.is_error is False
            assert len(call_b.content) > 0
            assert call_b.content[0].text == "[Server B Result for '25 * 4 + 10']"

            # 8. Execute another tool on Server B: 'text_transform' -> 'MCP HUB'
            call_b_transform = await session.call_tool(
                "text_server__text_transform",
                arguments={"text": "mcp hub gateway", "mode": "uppercase"},
            )
            assert call_b_transform.is_error is False
            assert call_b_transform.content[0].text == "MCP HUB GATEWAY"

            # 9. Test dynamic update: Disable Server B via REST API
            disable_resp = await rest_client.patch(
                f"/api/v1/servers/{server_b_id}",
                json={"enabled": False},
            )
            assert disable_resp.status_code == 200

            # Refresh tools via client: Server B tools must be removed dynamically
            tools_res_after_disable = await session.list_tools()
            names_after_disable = [t.name for t in tools_res_after_disable.tools]
            assert "math_server__calculate" in names_after_disable
            assert "text_server__calculate" not in names_after_disable
            assert "text_server__text_transform" not in names_after_disable

            # Calling a tool on the disabled server fails cleanly without whole-system crash
            disabled_call = await session.call_tool(
                "text_server__calculate",
                arguments={"expression": "1 + 1"},
            )
            assert disabled_call.is_error is True

            # Server A tools continue to work uninterrupted
            echo_call = await session.call_tool(
                "math_server__echo",
                arguments={"message": "hello gateway", "reverse": True},
            )
            assert echo_call.is_error is False
            assert echo_call.content[0].text == "yawetag olleh"

            # 10. Re-enable Server B via REST API
            enable_resp = await rest_client.patch(
                f"/api/v1/servers/{server_b_id}",
                json={"enabled": True},
            )
            assert enable_resp.status_code == 200
            refresh_b = await rest_client.post(f"/api/v1/servers/{server_b_id}/refresh-tools")
            assert refresh_b.status_code == 200

            # Verify tools dynamically reappear
            tools_res_re_enabled = await session.list_tools()
            names_re_enabled = [t.name for t in tools_res_re_enabled.tools]
            assert "text_server__calculate" in names_re_enabled

            # Execute Server B tool again successfully
            call_b_resumed = await session.call_tool(
                "text_server__calculate",
                arguments={"expression": "50 + 50"},
            )
            assert call_b_resumed.is_error is False
            assert call_b_resumed.content[0].text == "[Server B Result for '50 + 50']"

        # 11. Verify execution audit logs in Hub database
        audit_res = await rest_client.get("/api/v1/executions")
        assert audit_res.status_code == 200
        audit_items = audit_res.json()["items"]
        assert len(audit_items) >= 4

        tool_names_in_audit = [item["tool_name"] for item in audit_items]
        assert "calculate" in tool_names_in_audit
        assert "text_transform" in tool_names_in_audit
        assert "echo" in tool_names_in_audit
