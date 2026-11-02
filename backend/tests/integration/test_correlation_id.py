"""Integration tests ensuring correlation ID is exposed in all API calls (success, preflight, and errors)."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_tool_router_service
from app.main import app
from app.schemas.tool import ToolExecuteResponse


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Test client bound to app ASGI transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


def _assert_valid_correlation_id(response) -> str:
    """Helper asserting x-correlation-id header is present, non-empty, and valid UUIDv4."""
    corr_id = response.headers.get("x-correlation-id")
    assert corr_id is not None, f"Response missing x-correlation-id header: {response.headers}"
    parsed_uuid = uuid.UUID(corr_id)
    assert str(parsed_uuid) == corr_id
    assert parsed_uuid.version == 4
    return corr_id


# --- 1. SUCCESSFUL API CALLS (200, 201, 204) ---


@pytest.mark.asyncio
async def test_correlation_id_exposed_on_successful_get_health(client: AsyncClient):
    """GET /health (200 OK) exposes x-correlation-id header."""
    response = await client.get("/health")
    assert response.status_code == 200
    _assert_valid_correlation_id(response)


@pytest.mark.asyncio
async def test_correlation_id_exposed_on_successful_get_ready(client: AsyncClient):
    """GET /ready (200 OK) exposes x-correlation-id header."""
    response = await client.get("/ready")
    assert response.status_code == 200
    _assert_valid_correlation_id(response)


@pytest.mark.asyncio
async def test_correlation_id_exposed_on_successful_get_metrics(client: AsyncClient):
    """GET /metrics (200 OK) exposes x-correlation-id header."""
    response = await client.get("/metrics")
    assert response.status_code == 200
    _assert_valid_correlation_id(response)


@pytest.mark.asyncio
async def test_correlation_id_exposed_on_successful_list_servers(client: AsyncClient):
    """GET /api/v1/servers (200 OK) exposes x-correlation-id header."""
    response = await client.get("/api/v1/servers")
    assert response.status_code == 200
    _assert_valid_correlation_id(response)


@pytest.mark.asyncio
async def test_correlation_id_exposed_on_successful_list_tools(client: AsyncClient):
    """GET /api/v1/tools (200 OK) exposes x-correlation-id header."""
    response = await client.get("/api/v1/tools")
    assert response.status_code == 200
    _assert_valid_correlation_id(response)


@pytest.mark.asyncio
async def test_correlation_id_exposed_on_successful_list_executions(client: AsyncClient):
    """GET /api/v1/executions (200 OK) exposes x-correlation-id header."""
    response = await client.get("/api/v1/executions")
    assert response.status_code == 200
    _assert_valid_correlation_id(response)


@pytest.mark.asyncio
async def test_correlation_id_exposed_on_successful_crud_lifecycle(client: AsyncClient):
    """POST (201 Created), GET (200 OK), and DELETE (204 No Content) all expose x-correlation-id."""
    payload = {
        "name": "corr-test-server",
        "description": "Server for trace header verification",
        "transport": "stdio",
        "stdio_config": {"command": "python3"},
        "enabled": True,
    }

    # 1. POST /api/v1/servers -> 201 Created
    create_res = await client.post("/api/v1/servers", json=payload)
    assert create_res.status_code == 201
    create_corr_id = _assert_valid_correlation_id(create_res)
    server_id = create_res.json()["id"]

    # 2. GET /api/v1/servers/{id} -> 200 OK
    get_res = await client.get(f"/api/v1/servers/{server_id}")
    assert get_res.status_code == 200
    get_corr_id = _assert_valid_correlation_id(get_res)
    assert get_corr_id != create_corr_id  # Unique per call

    # 3. DELETE /api/v1/servers/{id} -> 204 No Content
    del_res = await client.delete(f"/api/v1/servers/{server_id}")
    assert del_res.status_code == 204
    del_corr_id = _assert_valid_correlation_id(del_res)
    assert del_corr_id != get_corr_id


@pytest.mark.asyncio
async def test_correlation_id_exposed_on_preflight_options(client: AsyncClient):
    """OPTIONS CORS preflight requests expose x-correlation-id header."""
    response = await client.options(
        "/api/v1/servers",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    _assert_valid_correlation_id(response)


@pytest.mark.asyncio
async def test_cors_exposes_correlation_id_on_actual_request(client: AsyncClient):
    """Actual cross-origin request includes Access-Control-Expose-Headers for x-correlation-id."""
    response = await client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200
    _assert_valid_correlation_id(response)
    expose_header = response.headers.get("access-control-expose-headers", "")
    assert "x-correlation-id" in expose_header.lower()


@pytest.mark.asyncio
async def test_correlation_id_exposed_on_tool_execute_success(client: AsyncClient):
    """Successful tool execution endpoint exposes x-correlation-id header and body."""
    server_uuid = uuid.uuid4()
    exec_uuid = uuid.uuid4()

    mock_router = MagicMock()

    async def mock_execute(server_id, tool_name, arguments, timeout=None):
        from app.core.logging import get_correlation_id

        return ToolExecuteResponse(
            execution_id=exec_uuid,
            server_id=server_uuid,
            tool_name="test_tool",
            is_error=False,
            content=[{"type": "text", "text": "executed successfully"}],
            duration_ms=12.5,
            executed_at=datetime.now(UTC),
            correlation_id=get_correlation_id(),
        )

    mock_router.execute_tool = mock_execute
    app.dependency_overrides[get_tool_router_service] = lambda: mock_router
    try:
        response = await client.post(
            f"/api/v1/servers/{server_uuid}/tools/test_tool/execute",
            json={"arguments": {"key": "val"}},
        )
        assert response.status_code == 200
        corr_id = _assert_valid_correlation_id(response)

        body = response.json()
        assert body["correlation_id"] == corr_id
        assert body["execution_id"] == str(exec_uuid)
    finally:
        app.dependency_overrides.pop(get_tool_router_service, None)


# --- 2. ERROR API CALLS (404, 422, APP EXCEPTION) ---


@pytest.mark.asyncio
async def test_correlation_id_exposed_on_404_not_found(client: AsyncClient):
    """404 error exposes x-correlation-id header and body."""
    response = await client.get("/api/v1/non-existent-route-path")
    assert response.status_code == 404
    corr_id = _assert_valid_correlation_id(response)

    data = response.json()
    assert "error" in data
    assert data["error"]["correlation_id"] == corr_id
    assert data["error"]["code"] == "HTTP_404"


@pytest.mark.asyncio
async def test_correlation_id_exposed_on_422_validation_error(client: AsyncClient):
    """422 Validation error exposes x-correlation-id header and body."""
    response = await client.post("/api/v1/servers", json={})
    assert response.status_code == 422
    corr_id = _assert_valid_correlation_id(response)

    data = response.json()
    assert "error" in data
    assert data["error"]["correlation_id"] == corr_id
    assert data["error"]["code"] == "ValidationError"


@pytest.mark.asyncio
async def test_correlation_id_exposed_on_app_exception(client: AsyncClient):
    """Domain/AppException error exposes x-correlation-id header and body."""
    random_uuid = str(uuid.uuid4())
    response = await client.get(f"/api/v1/servers/{random_uuid}")
    assert response.status_code == 404
    corr_id = _assert_valid_correlation_id(response)

    data = response.json()
    assert "error" in data
    assert data["error"]["correlation_id"] == corr_id
    assert data["error"]["code"] == "ServerNotFoundError"


# --- 3. INTERNAL GENERATION INTEGRITY ---


@pytest.mark.asyncio
async def test_internal_correlation_id_not_client_controlled(client: AsyncClient):
    """Backend generates correlation ID internally, ignoring client-supplied headers."""
    client_supplied_id = "client-spoofed-trace-id-999"
    response = await client.get("/health", headers={"X-Correlation-ID": client_supplied_id})
    assert response.status_code == 200

    corr_id = _assert_valid_correlation_id(response)
    assert corr_id != client_supplied_id
