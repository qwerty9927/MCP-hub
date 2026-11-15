"""Every account sees and acts on only its own Servers, Tools, Executions and Sessions."""

from uuid import UUID, uuid4

import pytest

from app.domain.execution_entity import ExecutionEntity
from app.domain.session_entity import SessionEntity
from app.domain.tool_entity import ToolEntity
from app.infrastructure.repositories.execution_repository import PostgresExecutionRepository
from app.infrastructure.repositories.session_repository import PostgresSessionRepository
from app.infrastructure.repositories.tool_repository import PostgresToolRepository

SERVER = {"name": "math", "transport": "stdio", "stdio_config": {"command": "python3", "args": ["x.py"]}}


@pytest.fixture
async def owned(async_client, user_id):
    """A server with one tool, one execution and one session, all belonging to the default account."""
    from datetime import UTC, datetime

    server = (await async_client.post("/api/v1/servers", json=SERVER)).json()
    server_id = UUID(server["id"])
    tool = ToolEntity(id=uuid4(), server_id=server_id, server_name="math", name="add", input_schema={}, user_id=user_id)
    await PostgresToolRepository().replace_server_tools(server_id, "math", [tool])
    session = await PostgresSessionRepository().create(SessionEntity(id=str(uuid4()), title="mine", user_id=user_id))
    execution = await PostgresExecutionRepository().create(
        ExecutionEntity(
            id=uuid4(),
            server_id=server_id,
            server_name="math",
            tool_name="add",
            arguments={},
            is_error=False,
            duration_ms=1.0,
            executed_at=datetime.now(UTC),
            session_id=session.id,
        )
    )
    return {"server": server_id, "tool": tool.id, "session": session.id, "execution": execution.id}


async def test_owner_sees_their_resources(async_client, owned):
    assert (await async_client.get(f"/api/v1/servers/{owned['server']}")).status_code == 200
    assert (await async_client.get(f"/api/v1/tools/{owned['tool']}")).status_code == 200
    assert (await async_client.get(f"/api/v1/executions/{owned['execution']}")).status_code == 200
    assert (await async_client.get(f"/api/v1/sessions/{owned['session']}")).status_code == 200
    assert (await async_client.get("/api/v1/servers")).json()["total"] == 1


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/servers/{server}"),
        ("patch", "/api/v1/servers/{server}"),
        ("delete", "/api/v1/servers/{server}"),
        ("post", "/api/v1/servers/{server}/connect"),
        ("post", "/api/v1/servers/{server}/disconnect"),
        ("post", "/api/v1/servers/{server}/test-connection"),
        ("post", "/api/v1/servers/{server}/refresh-tools"),
        ("get", "/api/v1/servers/{server}/tools"),
        ("post", "/api/v1/servers/{server}/tools/add/execute"),
        ("get", "/api/v1/tools/{tool}"),
        ("get", "/api/v1/executions/{execution}"),
        ("get", "/api/v1/sessions/{session}"),
        ("get", "/api/v1/sessions/{session}/tool-calls"),
        ("get", "/api/v1/sessions/{session}/tool-calls/{execution}"),
    ],
)
async def test_other_account_gets_404(other_user_client, owned, method, path):
    url = path.format(**owned)
    kwargs = {"json": {"enabled": False}} if method == "patch" else {"json": {"arguments": {}}} if path.endswith("execute") else {}

    res = await getattr(other_user_client, method)(url, **kwargs)

    assert res.status_code == 404, (url, res.status_code, res.text)


async def test_other_account_lists_are_empty(other_user_client, owned):
    for path in ("/api/v1/servers", "/api/v1/tools", "/api/v1/executions", "/api/v1/sessions"):
        assert (await other_user_client.get(path)).json()["total"] == 0, path
    metrics = (await other_user_client.get("/api/v1/system/metrics")).json()
    assert metrics["total_servers"] == 0 and metrics["total_executions"] == 0


async def test_foreign_session_cannot_be_used_for_execution(other_user_client, owned):
    mine = (await other_user_client.post("/api/v1/servers", json=SERVER)).json()

    res = await other_user_client.post(
        f"/api/v1/servers/{mine['id']}/tools/add/execute", json={"arguments": {}, "session_id": owned["session"]}
    )

    assert res.status_code == 404
    assert "Session" in res.json()["error"]["message"]


async def test_server_names_are_unique_per_account(async_client, other_user_client, owned):
    assert (await async_client.post("/api/v1/servers", json=SERVER)).status_code == 409
    assert (await other_user_client.post("/api/v1/servers", json=SERVER)).status_code == 201


@pytest.mark.parametrize("path", ["/api/v1/servers", "/api/v1/tools", "/api/v1/executions", "/api/v1/sessions", "/api/v1/system/metrics"])
async def test_rest_api_requires_login(anon_client, path):
    res = await anon_client.get(path)

    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


async def test_probes_stay_open(anon_client):
    assert (await anon_client.get("/health")).status_code == 200
    assert (await anon_client.get("/api/v1/system/health")).status_code == 200
    assert (await anon_client.get("/ready")).status_code == 200
