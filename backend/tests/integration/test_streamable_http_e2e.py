"""Integration tests verifying streamable-http transport end-to-end."""

import threading
import time

import pytest
import uvicorn
from httpx import AsyncClient
from mcp.server.mcpserver import MCPServer

# Build mock HTTP MCP server
http_mcp = MCPServer("demo-http-server")


@http_mcp.tool()
def multiply(x: int, y: int) -> int:
    """Multiply two integers."""
    return x * y


@pytest.fixture(scope="module")
def http_mcp_server_url():
    """Spin up local streamable-http MCP server on an ephemeral port."""
    starlette_app = http_mcp.streamable_http_app()
    port = 8925
    config = uvicorn.Config(starlette_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to bind
    time.sleep(0.5)

    yield f"http://127.0.0.1:{port}/mcp"

    server.should_exit = True


async def test_streamable_http_server_lifecycle(async_client: AsyncClient, http_mcp_server_url: str):
    """Test full cycle of streamable-http server: register, connect, discover, execute."""
    # 1. Register HTTP MCP server
    payload = {
        "name": "remote-http-server",
        "description": "Streamable HTTP MCP Server",
        "transport": "streamable-http",
        "http_config": {
            "url": http_mcp_server_url,
            "headers": {"X-Test-Token": "token123"},
        },
        "enabled": True,
    }
    create_res = await async_client.post("/api/v1/servers", json=payload)
    assert create_res.status_code == 201, create_res.text
    server = create_res.json()
    server_id = server["id"]

    # 2. Test Connection
    test_res = await async_client.post(f"/api/v1/servers/{server_id}/test-connection")
    assert test_res.status_code == 200
    assert test_res.json()["success"] is True
    assert test_res.json()["tools_count"] == 1

    # 3. Connect Server
    conn_res = await async_client.post(f"/api/v1/servers/{server_id}/connect")
    assert conn_res.status_code == 200
    assert conn_res.json()["health_status"] == "HEALTHY"

    # 4. Discover Tools
    tools_res = await async_client.get(f"/api/v1/servers/{server_id}/tools")
    assert tools_res.status_code == 200
    tools = tools_res.json()["items"]
    assert len(tools) == 1
    assert tools[0]["name"] == "multiply"

    # 5. Execute Tool 'multiply'
    exec_res = await async_client.post(
        f"/api/v1/servers/{server_id}/tools/multiply/execute",
        json={"arguments": {"x": 7, "y": 8}},
    )
    assert exec_res.status_code == 200, exec_res.text
    exec_data = exec_res.json()
    assert exec_data["is_error"] is False
    assert any("56" in str(c) for c in exec_data["content"])

    # 6. Disconnect
    disc_res = await async_client.post(f"/api/v1/servers/{server_id}/disconnect")
    assert disc_res.status_code == 200
    assert disc_res.json()["health_status"] == "DISCONNECTED"
