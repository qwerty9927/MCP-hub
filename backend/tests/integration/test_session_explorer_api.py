"""Integration tests for MCP Session Explorer REST endpoints."""

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.execution_entity import ExecutionEntity
from app.infrastructure.repositories.execution_repo import PostgresExecutionRepository

DEMO_SERVER = str(Path(__file__).resolve().parent.parent.parent / "demo_server" / "server.py")


@pytest.mark.asyncio
async def test_session_explorer_api_lifecycle(async_client: AsyncClient):
    """Verify complete HTTP API lifecycle for Session Explorer."""
    # 1. Create a session explicitly
    create_resp = await async_client.post(
        "/api/v1/sessions",
        json={
            "title": "Interactive Claude Session",
            "metadata": {"client": "claude-code", "env": "testing"},
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    session_data = create_resp.json()
    session_id = session_data["id"]
    assert session_data["title"] == "Interactive Claude Session"
    assert session_data["status"] == "active"
    assert session_data["total_tool_calls"] == 0

    # 2. List sessions
    list_resp = await async_client.get("/api/v1/sessions?page=1&page_size=10")
    assert list_resp.status_code == 200, list_resp.text
    list_json = list_resp.json()
    assert list_json["total"] >= 1
    session_ids = [s["id"] for s in list_json["items"]]
    assert session_id in session_ids

    # Search filter
    search_resp = await async_client.get("/api/v1/sessions?search=Interactive")
    assert search_resp.status_code == 200
    assert any(s["id"] == session_id for s in search_resp.json()["items"])

    # Status filter
    status_resp = await async_client.get("/api/v1/sessions?status=active")
    assert status_resp.status_code == 200
    assert any(s["id"] == session_id for s in status_resp.json()["items"])

    # 3. Register a test MCP server
    server_resp = await async_client.post(
        "/api/v1/servers",
        json={
            "name": "session-test-server",
            "transport": "stdio",
            "stdio_config": {
                "command": sys.executable,
                "args": [DEMO_SERVER],
            },
            "enabled": True,
        },
    )
    assert server_resp.status_code == 201, server_resp.text
    server_id = server_resp.json()["id"]

    # 4. Connect server to discover tools
    connect_resp = await async_client.post(f"/api/v1/servers/{server_id}/connect")
    assert connect_resp.status_code == 200

    # 5. Execute tool linked to the session
    exec_resp = await async_client.post(
        f"/api/v1/servers/{server_id}/tools/calculate/execute",
        json={
            "arguments": {"expression": "50 * 2 + 10"},
            "session_id": session_id,
        },
    )
    assert exec_resp.status_code == 200, exec_resp.text
    exec_data = exec_resp.json()
    call_id = exec_data["execution_id"]
    assert exec_data["is_error"] is False

    # 6. Retrieve session details - verify aggregated metrics
    detail_resp = await async_client.get(f"/api/v1/sessions/{session_id}")
    assert detail_resp.status_code == 200, detail_resp.text
    detail_json = detail_resp.json()
    assert detail_json["id"] == session_id
    assert detail_json["total_tool_calls"] == 1
    assert detail_json["successful_tool_calls"] == 1
    assert detail_json["failed_tool_calls"] == 0

    # 7. List tool calls within the session
    calls_resp = await async_client.get(f"/api/v1/sessions/{session_id}/tool-calls?order=asc")
    assert calls_resp.status_code == 200, calls_resp.text
    calls_json = calls_resp.json()
    assert calls_json["total"] == 1
    assert len(calls_json["items"]) == 1
    item = calls_json["items"][0]
    assert item["id"] == call_id
    assert item["session_id"] == session_id
    assert item["tool_name"] == "calculate"
    assert item["status"] == "completed"
    assert item["arguments"] == {"expression": "50 * 2 + 10"}

    # 8. Retrieve specific tool call detail
    single_call_resp = await async_client.get(f"/api/v1/sessions/{session_id}/tool-calls/{call_id}")
    assert single_call_resp.status_code == 200, single_call_resp.text
    single_json = single_call_resp.json()
    assert single_json["id"] == call_id
    assert single_json["tool_name"] == "calculate"

    # 9. Verify 404 on nonexistent session and call
    fake_session = uuid4().hex
    missing_session_resp = await async_client.get(f"/api/v1/sessions/{fake_session}")
    assert missing_session_resp.status_code == 404

    missing_call_resp = await async_client.get(
        f"/api/v1/sessions/{session_id}/tool-calls/{uuid4()}"
    )
    assert missing_call_resp.status_code == 404


@pytest.mark.asyncio
async def test_session_explorer_sensitive_masking(async_client: AsyncClient):
    """Verify tool call arguments and responses mask sensitive keys."""
    exec_repo = PostgresExecutionRepository()

    # 1. Create dummy session
    session_res = await async_client.post(
        "/api/v1/sessions",
        json={"title": "Sensitive Session"},
    )
    assert session_res.status_code == 201
    session_id = session_res.json()["id"]

    # 2. Register a server to satisfy foreign key
    server_res = await async_client.post(
        "/api/v1/servers",
        json={
            "name": "auth-server",
            "transport": "stdio",
            "stdio_config": {"command": sys.executable, "args": [DEMO_SERVER]},
            "enabled": True,
        },
    )
    assert server_res.status_code == 201
    server_id = server_res.json()["id"]

    # Insert an execution directly with sensitive parameters
    call_id = uuid4()
    await exec_repo.create(
        ExecutionEntity(
            id=call_id,
            server_id=server_id,
            server_name="auth-server",
            tool_name="authenticate",
            arguments={
                "username": "admin",
                "password": "SuperSecretPassword123!",
                "api_key": "key_xyz",
            },
            is_error=False,
            duration_ms=12.0,
            executed_at=datetime.now(UTC),
            session_id=session_id,
            status="completed",
            response={
                "content": [{"type": "text", "text": "Token generated"}],
                "token": "jwt_secret_token",
            },
        )
    )

    # Fetch session tool call
    resp = await async_client.get(f"/api/v1/sessions/{session_id}/tool-calls/{call_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["arguments"]["username"] == "admin"
    assert data["arguments"]["password"] == "***MASKED***"
    assert data["arguments"]["api_key"] == "***MASKED***"
    assert data["response"]["token"] == "***MASKED***"
