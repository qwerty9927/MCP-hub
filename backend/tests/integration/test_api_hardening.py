"""Regression tests for API defects found in review: readiness, query validation, error responses and account checks."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

import app.infrastructure.database as db_module
from app.api.dependencies import get_database
from app.core.config import get_settings
from app.domain.tool_entity import ToolEntity
from app.infrastructure.repositories.server_repository import PostgresServerRepository
from app.infrastructure.repositories.tool_repository import PostgresToolRepository
from app.main import app
from app.models.user_model import UserModel

HTTP_SERVER = {"name": "remote", "transport": "streamable-http", "http_config": {"url": "https://mcp.example.com/mcp"}}


# --- /ready reports the database ---


async def test_ready_checks_the_database(anon_client: AsyncClient):
    res = await anon_client.get("/ready")
    assert res.status_code == 200
    assert res.json()["checks"]["database"] is True


async def test_ready_is_503_when_the_database_is_down(anon_client: AsyncClient):
    class Unreachable:
        async def __aenter__(self):
            raise ConnectionRefusedError("database is down")

        async def __aexit__(self, *exc):
            return False

    class DatabaseDown:
        def session(self):
            return Unreachable()

    app.dependency_overrides[get_database] = DatabaseDown
    try:
        res = await anon_client.get("/ready")
    finally:
        app.dependency_overrides.pop(get_database, None)
    assert res.status_code == 503
    assert res.json()["status"] == "not_ready"
    assert res.json()["checks"]["database"] is False


# --- list query parameters are validated, not passed to getattr ---


@pytest.mark.parametrize("sort_by", ["metadata", "to_domain", "registry", "user_id", "http_config"])
async def test_unknown_sort_field_is_422(async_client: AsyncClient, sort_by):
    res = await async_client.get("/api/v1/servers", params={"sort_by": sort_by})
    assert res.status_code == 422, res.text


@pytest.mark.parametrize("sort_by", ["created_at", "name", "updated_at"])
async def test_documented_sort_fields_work(async_client: AsyncClient, sort_by):
    assert (await async_client.post("/api/v1/servers", json=HTTP_SERVER)).status_code == 201
    res = await async_client.get("/api/v1/servers", params={"sort_by": sort_by, "sort_order": "asc"})
    assert res.status_code == 200
    assert res.json()["total"] == 1


# --- deleting a server is all or nothing ---


async def test_failed_server_delete_keeps_its_tools(async_client: AsyncClient, user_id, monkeypatch):
    created = await async_client.post("/api/v1/servers", json=HTTP_SERVER)
    server_id = UUID(created.json()["id"])
    tool = ToolEntity(
        id=uuid4(),
        server_id=server_id,
        server_name="remote",
        name="echo",
        description="Echo text",
        input_schema={"type": "object"},
        availability_status="AVAILABLE",
        last_discovered_at=datetime.now(UTC),
        user_id=user_id,
    )
    await PostgresToolRepository().replace_server_tools(server_id, "remote", [tool])

    async def fail(self, server_id):
        raise RuntimeError("database went away mid-delete")

    monkeypatch.setattr(PostgresServerRepository, "delete", fail)
    failing = AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver")
    async with failing:
        res = await failing.delete(f"/api/v1/servers/{server_id}", headers=dict(async_client.headers))
    assert res.status_code == 500
    monkeypatch.undo()

    tools = await async_client.get("/api/v1/tools", params={"server_id": str(server_id)})
    assert tools.json()["total"] == 1, "the server still exists, so its tools must too"


async def test_server_delete_removes_its_tools(async_client: AsyncClient, user_id):
    created = await async_client.post("/api/v1/servers", json=HTTP_SERVER)
    server_id = UUID(created.json()["id"])
    tool = ToolEntity(
        id=uuid4(),
        server_id=server_id,
        server_name="remote",
        name="echo",
        description=None,
        input_schema={"type": "object"},
        availability_status="AVAILABLE",
        last_discovered_at=datetime.now(UTC),
        user_id=user_id,
    )
    await PostgresToolRepository().replace_server_tools(server_id, "remote", [tool])

    assert (await async_client.delete(f"/api/v1/servers/{server_id}")).status_code == 204
    assert (await async_client.get("/api/v1/tools")).json()["total"] == 0


# --- a deleted account's console token stops working ---


async def test_token_of_deleted_account_is_rejected(async_client: AsyncClient, user_id):
    assert (await async_client.get("/api/v1/servers")).status_code == 200

    async with db_module.database.session() as session:
        await session.execute(delete(UserModel).where(UserModel.id == str(user_id)))
        await session.commit()

    res = await async_client.get("/api/v1/servers")
    assert res.status_code == 401


# --- error responses keep their headers, including CORS on 500s ---


async def test_http_exception_headers_are_kept(async_client: AsyncClient):
    res = await async_client.put("/api/v1/auth/me")
    assert res.status_code == 405
    assert "GET" in res.headers["Allow"]
    assert res.headers["X-Correlation-ID"]


async def test_unhandled_error_has_cors_headers(async_client: AsyncClient, monkeypatch):
    origin = get_settings().CORS_ORIGINS[0]

    async def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(PostgresServerRepository, "list", boom)
    failing = AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver")
    async with failing:
        res = await failing.get("/api/v1/servers", headers={**dict(async_client.headers), "Origin": origin})
    assert res.status_code == 500
    assert res.headers["Access-Control-Allow-Origin"] == origin
    assert res.headers["X-Correlation-ID"]
    assert res.json()["error"]["code"] == "InternalServerError"


async def test_unhandled_error_has_no_cors_headers_for_other_origins(async_client: AsyncClient, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(PostgresServerRepository, "list", boom)
    failing = AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver")
    async with failing:
        res = await failing.get("/api/v1/servers", headers={**dict(async_client.headers), "Origin": "https://evil.example"})
    assert res.status_code == 500
    assert "Access-Control-Allow-Origin" not in res.headers


# --- OpenAPI documents the error envelope ---


async def test_openapi_documents_error_responses(anon_client: AsyncClient):
    schema = (await anon_client.get("/openapi.json")).json()
    get_server = schema["paths"]["/api/v1/servers/{server_id}"]["get"]["responses"]

    for code in ("401", "404", "422"):
        assert code in get_server, f"GET /servers/{{id}} does not document {code}"
        assert get_server[code]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorResponse"
    assert "HTTPValidationError" not in str(get_server)


# --- /metrics counts every server, not the first 1000 ---


async def test_metrics_count_more_than_a_thousand_servers(async_client: AsyncClient, user_id):
    from sqlalchemy import insert

    from app.models.server_model import ServerModel

    now = datetime.now(UTC)
    rows = [
        {
            "id": str(uuid4()),
            "name": f"server-{i}",
            "transport": "streamable-http",
            "http_config": {"url": "https://mcp.example.com/mcp", "headers": {}},
            "enabled": True,
            "health_status": "HEALTHY" if i % 2 == 0 else "UNHEALTHY",
            "user_id": str(user_id),
            "created_at": now,
            "updated_at": now,
        }
        for i in range(1002)
    ]
    async with db_module.database.session() as session:
        await session.execute(insert(ServerModel), rows)
        await session.commit()

    metrics = (await async_client.get("/api/v1/system/metrics")).json()
    assert metrics["total_servers"] == 1002
    assert metrics["healthy_servers"] == 501


# --- request bodies reject unknown fields and mismatched transport config ---


@pytest.mark.parametrize(
    "payload",
    [
        {**HTTP_SERVER, "enable": False},
        {**HTTP_SERVER, "http_config": {"url": "https://mcp.example.com/mcp", "header": {"X": "1"}}},
        {"name": "s", "transport": "stdio", "stdio_config": {"command": "python", "args": ["s.py"], "envs": {}}},
        {**HTTP_SERVER, "stdio_config": {"command": "python", "args": ["s.py"]}},
    ],
)
async def test_create_rejects_unknown_fields_and_other_transport_config(async_client: AsyncClient, payload):
    res = await async_client.post("/api/v1/servers", json=payload)
    assert res.status_code == 422, res.text


@pytest.mark.parametrize(
    "patch",
    [
        {"enable": False},
        {"http_confg": {"url": "https://mcp.example.com/mcp"}},
        {"transport": "streamable-http", "stdio_config": {"command": "python", "args": ["s.py"]}},
        {"transport": "stdio", "http_config": {"url": "https://mcp.example.com/mcp"}},
    ],
)
async def test_update_rejects_unknown_fields_and_other_transport_config(async_client: AsyncClient, patch):
    created = await async_client.post("/api/v1/servers", json=HTTP_SERVER)
    res = await async_client.patch(f"/api/v1/servers/{created.json()['id']}", json=patch)
    assert res.status_code == 422, res.text


async def test_update_with_masked_header_keeps_the_stored_secret(async_client: AsyncClient, user_id):
    """The console's edit form sends back the masked value it was shown; that must not overwrite the secret."""
    created = await async_client.post(
        "/api/v1/servers",
        json={**HTTP_SERVER, "http_config": {"url": "https://mcp.example.com/mcp", "headers": {"X-Auth-Token": "real-secret"}}},
    )
    server_id = created.json()["id"]
    shown = created.json()["connection_config"]["headers"]
    assert shown == {"X-Auth-Token": "********"}

    res = await async_client.patch(
        f"/api/v1/servers/{server_id}",
        json={"http_config": {"url": "https://mcp.example.com/v2/mcp", "headers": {**shown, "X-Region": "eu"}}},
    )
    assert res.status_code == 200, res.text

    stored = await PostgresServerRepository().get_by_id(UUID(server_id), user_id=user_id)
    assert stored.http_config.headers == {"X-Auth-Token": "real-secret", "X-Region": "eu"}
    assert stored.http_config.url == "https://mcp.example.com/v2/mcp"


# --- a hostname that resolves to a private address is refused when the server is saved ---


async def test_create_refuses_a_name_that_resolves_to_a_private_address(async_client: AsyncClient, monkeypatch):
    import asyncio
    import socket

    monkeypatch.setattr(get_settings(), "ALLOW_PRIVATE_NETWORK_HTTP", False)

    async def resolves_to_loopback(self, host, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    monkeypatch.setattr(asyncio.get_running_loop().__class__, "getaddrinfo", resolves_to_loopback)
    payload = {**HTTP_SERVER, "http_config": {"url": "https://rebind.example.com/mcp"}}
    res = await async_client.post("/api/v1/servers", json=payload)
    assert res.status_code == 403
    assert "resolves to" in res.json()["error"]["message"]


# --- one log line per request, with its status; one traceback per unhandled error ---


async def test_request_log_line_has_the_status_code(async_client: AsyncClient, caplog):
    caplog.set_level("INFO", logger="mcp_hub")
    await async_client.get("/api/v1/servers/00000000-0000-0000-0000-000000000000")
    finished = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Finished GET /api/v1/servers/")]
    assert len(finished) == 1
    assert " 404 " in finished[0]


async def test_unhandled_error_is_logged_with_one_traceback(async_client: AsyncClient, monkeypatch, caplog):
    async def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(PostgresServerRepository, "list", boom)
    caplog.set_level("INFO", logger="mcp_hub")
    failing = AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver")
    async with failing:
        await failing.get("/api/v1/servers", headers=dict(async_client.headers))

    with_traceback = [r for r in caplog.records if r.exc_info]
    assert len(with_traceback) == 1
    assert any(r.getMessage().startswith("Failed GET /api/v1/servers") and " 500 " in r.getMessage() for r in caplog.records)


async def test_update_with_masked_value_for_an_unknown_header_is_422(async_client: AsyncClient):
    """A masked value only means "keep it" for a header that is stored; anything else would save the mask itself."""
    created = await async_client.post(
        "/api/v1/servers",
        json={**HTTP_SERVER, "http_config": {"url": "https://mcp.example.com/mcp", "headers": {"X-Auth-Token": "real-secret"}}},
    )
    res = await async_client.patch(
        f"/api/v1/servers/{created.json()['id']}",
        json={"http_config": {"url": "https://mcp.example.com/mcp", "headers": {"X-Api-Token": "********"}}},
    )
    assert res.status_code == 422, res.text
