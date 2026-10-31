"""Integration tests for Phase 2: Multi-server aggregation, duplicate tool handling, and execution history."""

import sys
from pathlib import Path

from httpx import AsyncClient

SERVER_A_SCRIPT = str(Path(__file__).resolve().parent.parent.parent / "demo_server" / "server.py")
SERVER_B_SCRIPT = str(Path(__file__).resolve().parent.parent.parent / "demo_server" / "server_b.py")


async def test_multi_server_aggregation_and_duplicate_tool_names(async_client: AsyncClient):
    """Register two distinct MCP servers that share a duplicate tool name ('calculate')

    and verify proper aggregation, qualified ID handling, and isolated routing.
    """
    # 1. Register Server A
    res_a = await async_client.post(
        "/api/v1/servers",
        json={
            "name": "math-server-a",
            "description": "Primary Math Server",
            "transport": "stdio",
            "stdio_config": {"command": sys.executable, "args": [SERVER_A_SCRIPT]},
            "enabled": True,
        },
    )
    assert res_a.status_code == 201
    server_a_id = res_a.json()["id"]

    # 2. Register Server B (also provides 'calculate')
    res_b = await async_client.post(
        "/api/v1/servers",
        json={
            "name": "text-server-b",
            "description": "Text Server with duplicate calculate tool",
            "transport": "stdio",
            "stdio_config": {"command": sys.executable, "args": [SERVER_B_SCRIPT]},
            "enabled": True,
        },
    )
    assert res_b.status_code == 201
    server_b_id = res_b.json()["id"]

    # 3. Connect both servers
    conn_a = await async_client.post(f"/api/v1/servers/{server_a_id}/connect")
    assert conn_a.status_code == 200
    assert conn_a.json()["health_status"] == "HEALTHY"

    conn_b = await async_client.post(f"/api/v1/servers/{server_b_id}/connect")
    assert conn_b.status_code == 200
    assert conn_b.json()["health_status"] == "HEALTHY"

    # 4. Aggregated Tool Catalog Check
    tools_res = await async_client.get("/api/v1/tools?page_size=50")
    assert tools_res.status_code == 200
    all_tools = tools_res.json()["items"]
    assert len(all_tools) >= 6

    # Verify duplicate tool name 'calculate' has two distinct qualified IDs
    calc_tools = [t for t in all_tools if t["name"] == "calculate"]
    assert len(calc_tools) == 2
    calc_ids = {t["id"] for t in calc_tools}
    assert f"{server_a_id}:calculate" in calc_ids
    assert f"{server_b_id}:calculate" in calc_ids

    # 5. Filter by Server A
    tools_a_res = await async_client.get(f"/api/v1/servers/{server_a_id}/tools")
    assert tools_a_res.status_code == 200
    server_a_tools = tools_a_res.json()["items"]
    assert len(server_a_tools) == 3
    assert all(t["server_id"] == server_a_id for t in server_a_tools)

    # 6. Filter by Server B
    tools_b_res = await async_client.get(f"/api/v1/servers/{server_b_id}/tools")
    assert tools_b_res.status_code == 200
    server_b_tools = tools_b_res.json()["items"]
    assert len(server_b_tools) == 3
    assert all(t["server_id"] == server_b_id for t in server_b_tools)

    # 7. Execute 'calculate' on Server A -> Math result
    exec_a = await async_client.post(
        f"/api/v1/servers/{server_a_id}/tools/calculate/execute",
        json={"arguments": {"expression": "15 + 25"}},
    )
    assert exec_a.status_code == 200
    data_a = exec_a.json()
    assert data_a["is_error"] is False
    assert any("40" in str(c) for c in data_a["content"])

    # 8. Execute 'calculate' on Server B -> Text server duplicate result
    exec_b = await async_client.post(
        f"/api/v1/servers/{server_b_id}/tools/calculate/execute",
        json={"arguments": {"expression": "15 + 25"}},
    )
    assert exec_b.status_code == 200
    data_b = exec_b.json()
    assert data_b["is_error"] is False
    assert any("[Server B Result" in str(c) for c in data_b["content"])

    # 9. Execute 'text_transform' on Server B
    exec_text = await async_client.post(
        f"/api/v1/servers/{server_b_id}/tools/text_transform/execute",
        json={"arguments": {"text": "hello mcp", "mode": "uppercase"}},
    )
    assert exec_text.status_code == 200
    assert any("HELLO MCP" in str(c) for c in exec_text.json()["content"])


async def test_execution_history_filtering_and_pagination(async_client: AsyncClient):
    """Test execution history logging, filtering by server/tool/status, and pagination."""
    # Register and connect server
    res = await async_client.post(
        "/api/v1/servers",
        json={
            "name": "audit-server",
            "transport": "stdio",
            "stdio_config": {"command": sys.executable, "args": [SERVER_A_SCRIPT]},
            "enabled": True,
        },
    )
    server_id = res.json()["id"]
    await async_client.post(f"/api/v1/servers/{server_id}/connect")

    # Run successful tool call
    await async_client.post(
        f"/api/v1/servers/{server_id}/tools/calculate/execute",
        json={"arguments": {"expression": "10 * 10"}},
    )
    # Run another successful call with different tool
    await async_client.post(
        f"/api/v1/servers/{server_id}/tools/echo/execute",
        json={"arguments": {"message": "audit check"}},
    )
    # Run a call with invalid arguments to trigger validation/error logging
    await async_client.post(
        f"/api/v1/servers/{server_id}/tools/calculate/execute",
        json={"arguments": {"expression": "invalid math !!!"}},
    )

    # 1. List all executions
    hist_all = await async_client.get("/api/v1/executions")
    assert hist_all.status_code == 200
    all_items = hist_all.json()["items"]
    assert len(all_items) >= 2

    # 2. Filter by tool_name
    hist_echo = await async_client.get("/api/v1/executions?tool_name=echo")
    assert hist_echo.status_code == 200
    echo_items = hist_echo.json()["items"]
    assert all(i["tool_name"] == "echo" for i in echo_items)

    # 3. Filter by server_id
    hist_server = await async_client.get(f"/api/v1/executions?server_id={server_id}")
    assert hist_server.status_code == 200
    assert hist_server.json()["total"] >= 2

    # 4. Pagination
    paged = await async_client.get("/api/v1/executions?page=1&page_size=1")
    assert paged.status_code == 200
    assert len(paged.json()["items"]) == 1
    assert paged.json()["page"] == 1
    assert paged.json()["page_size"] == 1
    assert paged.json()["total_pages"] >= 2


async def test_server_disabled_blocks_execution(async_client: AsyncClient):
    """Disabling a server must prevent tool executions on it."""
    res = await async_client.post(
        "/api/v1/servers",
        json={
            "name": "toggle-server",
            "transport": "stdio",
            "stdio_config": {"command": sys.executable, "args": [SERVER_A_SCRIPT]},
            "enabled": True,
        },
    )
    server_id = res.json()["id"]
    await async_client.post(f"/api/v1/servers/{server_id}/connect")

    # Disable server
    patch_res = await async_client.patch(
        f"/api/v1/servers/{server_id}",
        json={"enabled": False},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["enabled"] is False

    # Attempt to execute tool on disabled server -> 400 ServerDisabledError
    exec_res = await async_client.post(
        f"/api/v1/servers/{server_id}/tools/echo/execute",
        json={"arguments": {"message": "should fail"}},
    )
    assert exec_res.status_code == 400
    assert "disabled" in exec_res.json()["error"]["message"].lower()
