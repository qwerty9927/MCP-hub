"""End-to-End integration tests using the local Demo MCP Server over stdio."""

import sys
from pathlib import Path

from httpx import AsyncClient

# Absolute path to demo server script
DEMO_SERVER_SCRIPT = str(Path(__file__).resolve().parent.parent.parent / "demo_server" / "server.py")


async def test_system_endpoints(async_client: AsyncClient):
    """Test system liveness, readiness, and metrics endpoints."""
    health_res = await async_client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"

    ready_res = await async_client.get("/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "ready"

    metrics_res = await async_client.get("/metrics")
    assert metrics_res.status_code == 200
    data = metrics_res.json()
    assert "active_sessions" in data
    assert "total_servers" in data


async def test_demo_server_full_lifecycle(async_client: AsyncClient):
    """Full lifecycle: register, test, connect, discover, execute, inspect audit log, disconnect."""
    # 1. Register demo server
    server_payload = {
        "name": "e2e-demo-server",
        "description": "Integration test demo MCP server",
        "transport": "stdio",
        "stdio_config": {
            "command": sys.executable,
            "args": [DEMO_SERVER_SCRIPT],
        },
        "enabled": True,
    }
    create_res = await async_client.post("/api/v1/servers", json=server_payload)
    assert create_res.status_code == 201, create_res.text
    server = create_res.json()
    server_id = server["id"]
    assert server["name"] == "e2e-demo-server"
    assert server["health_status"] == "UNKNOWN"

    # 2. Test Connection
    test_res = await async_client.post(f"/api/v1/servers/{server_id}/test-connection")
    assert test_res.status_code == 200
    test_data = test_res.json()
    assert test_data["success"] is True
    assert test_data["tools_count"] >= 3
    assert test_data["latency_ms"] > 0

    # 3. Connect to Server
    conn_res = await async_client.post(f"/api/v1/servers/{server_id}/connect")
    assert conn_res.status_code == 200
    conn_data = conn_res.json()
    assert conn_data["health_status"] == "HEALTHY"
    assert conn_data["discovered_tool_count"] >= 3

    # 4. Discover Tools via Unified Catalog
    tools_res = await async_client.get("/api/v1/tools")
    assert tools_res.status_code == 200
    tools_data = tools_res.json()
    tool_names = [t["name"] for t in tools_data["items"]]
    assert "calculate" in tool_names
    assert "echo" in tool_names
    assert "system_ping" in tool_names

    # Check server-specific tools endpoint
    server_tools_res = await async_client.get(f"/api/v1/servers/{server_id}/tools")
    assert server_tools_res.status_code == 200
    assert len(server_tools_res.json()["items"]) >= 3

    # 5. Execute Tool 'calculate': 25 * 4 + 10 = 110
    calc_exec_res = await async_client.post(
        f"/api/v1/servers/{server_id}/tools/calculate/execute",
        json={"arguments": {"expression": "25 * 4 + 10"}},
    )
    assert calc_exec_res.status_code == 200, calc_exec_res.text
    calc_data = calc_exec_res.json()
    assert calc_data["is_error"] is False
    assert any("110" in str(c) for c in calc_data["content"])
    assert calc_data["duration_ms"] > 0
    execution_id = calc_data["execution_id"]

    # 6. Execute Tool 'echo'
    echo_exec_res = await async_client.post(
        f"/api/v1/servers/{server_id}/tools/echo/execute",
        json={"arguments": {"message": "hello antigravity", "uppercase": True}},
    )
    assert echo_exec_res.status_code == 200
    echo_data = echo_exec_res.json()
    assert echo_data["is_error"] is False
    assert any("HELLO ANTIGRAVITY" in str(c) for c in echo_data["content"])

    # 7. Execute Tool 'system_ping'
    ping_exec_res = await async_client.post(
        f"/api/v1/servers/{server_id}/tools/system_ping/execute",
        json={"arguments": {}},
    )
    assert ping_exec_res.status_code == 200
    ping_data = ping_exec_res.json()
    assert ping_data["is_error"] is False

    # 8. Check Execution History Audit Log
    exec_history_res = await async_client.get("/api/v1/executions")
    assert exec_history_res.status_code == 200
    history_items = exec_history_res.json()["items"]
    assert len(history_items) >= 3

    single_exec_res = await async_client.get(f"/api/v1/executions/{execution_id}")
    assert single_exec_res.status_code == 200
    assert single_exec_res.json()["tool_name"] == "calculate"

    # 9. Disconnect Server
    disc_res = await async_client.post(f"/api/v1/servers/{server_id}/disconnect")
    assert disc_res.status_code == 200
    assert disc_res.json()["health_status"] == "DISCONNECTED"

    # 10. Delete Server
    del_res = await async_client.delete(f"/api/v1/servers/{server_id}")
    assert del_res.status_code == 204

    # Verify deleted
    get_res = await async_client.get(f"/api/v1/servers/{server_id}")
    assert get_res.status_code == 404
