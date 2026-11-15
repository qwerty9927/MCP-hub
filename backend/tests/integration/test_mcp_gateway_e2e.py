"""End-to-End integration test for the MCP Server Streamable HTTP transport.

Verifies:
1. Hub connects to two independent downstream MCP servers (Server A & Server B).
2. MCP Client connects to the Hub's unified '/mcp' Streamable HTTP endpoint.
3. Client receives strictly the two supported meta-tools: SEARCH_TOOLS and MULTI_EXECUTE_TOOLS.
4. Client discovers tools across servers via SEARCH_TOOLS.
5. Client invokes tools from Server A and Server B via MULTI_EXECUTE_TOOLS.
6. Dynamic updates (disabling/re-enabling downstream servers) update SEARCH_TOOLS candidates.
7. Execution audit logs record tool invocations.
"""

import asyncio
import json
import socket
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from app.core.constants.meta_tools import (
    MULTI_EXECUTE_TOOLS_NAME,
    SEARCH_TOOLS_NAME,
)
from app.main import app
from tests.conftest import login_headers

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
    server_mcp_url = f"{base_url}/mcp"

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as rest_client:
        # 0. Sign in, and give each MCP client its own API key
        rest_client.headers.update(await login_headers(rest_client, "agent-owner@test.local"))
        handshake_key = (await rest_client.post("/api/v1/auth/api-keys", json={"name": "handshake client"})).json()["key"]
        sessionless_key = (await rest_client.post("/api/v1/auth/api-keys", json={"name": "sessionless client"})).json()["key"]

        unauthenticated = await rest_client.post(
            "/mcp", headers={"Authorization": ""}, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )
        assert unauthenticated.status_code == 401

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

        # 4. Connect MCP Client to the Hub's /mcp Streamable HTTP endpoint
        async with (
            create_mcp_http_client(headers={"x-api-key": handshake_key}) as handshake_http,
            streamable_http_client(server_mcp_url, http_client=handshake_http) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            init_res = await session.initialize()
            assert init_res.server_info.name == "mcp-hub-server"
            assert init_res.capabilities.tools is not None
            # The tool list is fixed, so the hub advertises no list-change notifications.
            assert init_res.capabilities.tools.list_changed is False

            # 5. List tools: strictly SEARCH_TOOLS and MULTI_EXECUTE_TOOLS
            tools_res = await session.list_tools()
            tool_names = [t.name for t in tools_res.tools]
            assert len(tool_names) == 2
            assert SEARCH_TOOLS_NAME in tool_names
            assert MULTI_EXECUTE_TOOLS_NAME in tool_names

            # 6. Discover candidate tools via SEARCH_TOOLS
            search_call = await session.call_tool(
                SEARCH_TOOLS_NAME,
                arguments={"queries": ["math calculate", "text transform"]},
            )
            assert search_call.is_error is False
            search_data = json.loads(search_call.content[0].text)
            discovered_slugs = [t["tool_slug"] for t in search_data["tools"]]
            assert "math_server__calculate" in discovered_slugs
            assert "text_server__text_transform" in discovered_slugs

            # 7. Execute tools on Server A & Server B via MULTI_EXECUTE_TOOLS
            multi_call = await session.call_tool(
                MULTI_EXECUTE_TOOLS_NAME,
                arguments={
                    "executions": [
                        {
                            "tool_slug": "math_server__calculate",
                            "arguments": {"expression": "25 * 4 + 10"},
                        },
                        {
                            "tool_slug": "text_server__text_transform",
                            "arguments": {"text": "mcp hub", "mode": "uppercase"},
                        },
                    ]
                },
            )
            assert multi_call.is_error is False
            multi_data = json.loads(multi_call.content[0].text)
            results = multi_data["results"]
            assert len(results) == 2
            assert results[0]["status"] == "success"
            assert results[0]["data"] == "110"
            assert results[1]["status"] == "success"
            assert results[1]["data"] == "MCP HUB"

            # 8. Test dynamic update: Disable Server B via REST API
            disable_resp = await rest_client.patch(
                f"/api/v1/servers/{server_b_id}",
                json={"enabled": False},
            )
            assert disable_resp.status_code == 200

            # SEARCH_TOOLS after disable: Server B tools must no longer be discoverable
            search_after_disable = await session.call_tool(
                SEARCH_TOOLS_NAME,
                arguments={"queries": ["text transform"]},
            )
            assert search_after_disable.is_error is False
            data_after = json.loads(search_after_disable.content[0].text)
            slugs_after = [t["tool_slug"] for t in data_after["tools"]]
            assert "text_server__text_transform" not in slugs_after

            # Calling a disabled tool via MULTI_EXECUTE_TOOLS fails cleanly with server disabled error
            multi_disabled_call = await session.call_tool(
                MULTI_EXECUTE_TOOLS_NAME,
                arguments={
                    "executions": [
                        {
                            "tool_slug": "text_server__calculate",
                            "arguments": {"expression": "1 + 1"},
                        }
                    ]
                },
            )
            assert multi_disabled_call.is_error is False
            disabled_res = json.loads(multi_disabled_call.content[0].text)["results"][0]
            assert disabled_res["status"] == "error"
            assert "disabled" in disabled_res["error"]

            # 9. Re-enable Server B via REST API
            enable_resp = await rest_client.patch(
                f"/api/v1/servers/{server_b_id}",
                json={"enabled": True},
            )
            assert enable_resp.status_code == 200
            refresh_b = await rest_client.post(f"/api/v1/servers/{server_b_id}/refresh-tools")
            assert refresh_b.status_code == 200

            # Verify Server B tools reappear in search
            search_re_enabled = await session.call_tool(
                SEARCH_TOOLS_NAME,
                arguments={"queries": ["text transform"]},
            )
            data_re_enabled = json.loads(search_re_enabled.content[0].text)
            slugs_re_enabled = [t["tool_slug"] for t in data_re_enabled["tools"]]
            assert "text_server__text_transform" in slugs_re_enabled

        # 10. A 2026-07-28 client: no initialize, no Mcp-Session-Id. The hub derives its session.
        async with (
            create_mcp_http_client(headers={"x-api-key": sessionless_key}) as sessionless_http,
            streamable_http_client(server_mcp_url, http_client=sessionless_http) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as modern,
        ):
            await modern.discover()
            assert len((await modern.list_tools()).tools) == 2
            for expression in ("1 + 1", "2 * 3"):
                call = await modern.call_tool(
                    MULTI_EXECUTE_TOOLS_NAME,
                    arguments={"executions": [{"tool_slug": "math_server__calculate", "arguments": {"expression": expression}}]},
                )
                assert json.loads(call.content[0].text)["results"][0]["status"] == "success"

        # 11. Stateless /mcp (ADR-0004): a leftover Mcp-Session-Id is ignored rather than answered with
        # 404 "Session not found", no initialize is needed, and there is no GET stream to open.
        mcp_headers = {
            "x-api-key": handshake_key,
            "accept": "application/json, text/event-stream",
            "mcp-protocol-version": "2025-11-25",
        }
        stale = await rest_client.post(
            "/mcp",
            headers={**mcp_headers, "mcp-session-id": "expired-session-from-before-a-restart"},
            json={"jsonrpc": "2.0", "id": 7, "method": "tools/list"},
        )
        assert stale.status_code == 200, stale.text
        assert "mcp-session-id" not in stale.headers
        assert len(stale.json()["result"]["tools"]) == 2
        assert (await rest_client.get("/mcp", headers=mcp_headers)).status_code == 405

        sessions = (await rest_client.get("/api/v1/sessions")).json()["items"]
        details = [(await rest_client.get(f"/api/v1/sessions/{s['id']}")).json() for s in sessions]
        assert {d["metadata"]["session_source"] for d in details} == {"derived"}
        # The modern client names itself in `_meta`; the handshake client's name died with its initialize,
        # so its User-Agent identifies it. The raw request in step 11 shares the handshake client's API key
        # but not its User-Agent, so it lands in a Session of its own.
        named = [d for d in details if d["metadata"].get("client_name")]
        unnamed = sorted((d for d in details if not d["metadata"].get("client_name")), key=lambda d: d["total_tool_calls"])
        assert len(named) == 1 and named[0]["total_tool_calls"] == 2
        assert len(unnamed) == 2
        raw_request, handshake_client = unnamed
        assert raw_request["total_tool_calls"] == 0
        assert handshake_client["total_tool_calls"] >= 2
        assert raw_request["metadata"]["user_agent"] != handshake_client["metadata"]["user_agent"]

        # 11. Verify execution audit logs in Hub database
        audit_res = await rest_client.get("/api/v1/executions")
        assert audit_res.status_code == 200
        audit_items = audit_res.json()["items"]
        assert len(audit_items) >= 2

        tool_names_in_audit = [item["tool_name"] for item in audit_items]
        assert "calculate" in tool_names_in_audit
        assert "text_transform" in tool_names_in_audit
