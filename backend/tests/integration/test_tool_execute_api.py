"""REST adapter over the Execution module: POST /servers/{id}/tools/{name}/execute status mapping."""

from uuid import UUID, uuid4

import pytest

from app.api.dependencies import get_tool_executor_service
from app.core.enums.server_enum import TransportType
from app.core.enums.session_enum import ToolCallStatus
from app.domain.server_entity import ServerEntity
from app.infrastructure.repositories.execution_repository import PostgresExecutionRepository
from app.infrastructure.repositories.server_repository import PostgresServerRepository
from app.infrastructure.repositories.session_repository import PostgresSessionRepository
from app.infrastructure.repositories.tool_repository import PostgresToolRepository
from app.main import app
from app.schemas.connection_schema import StdioConfig
from app.services.server_registry import ServerRegistryService
from app.services.tool_catalog import ToolCatalogService
from app.services.tool_executor import ToolExecutor
from tests.fake_downstream import FakeDownstream
from tests.fake_embeddings import FakeEmbeddingService


@pytest.fixture
async def server(user_id):
    return await PostgresServerRepository().create(
        ServerEntity(name="Math Server", transport=TransportType.STDIO, stdio_config=StdioConfig(command="python3"), user_id=user_id)
    )


@pytest.fixture(autouse=True)
def fake_executor():
    downstream = FakeDownstream()
    executor = ToolExecutor(
        server_registry=ServerRegistryService(server_repository=PostgresServerRepository()),
        connection_manager=downstream,
        tool_catalog=ToolCatalogService(tool_repository=PostgresToolRepository(), embedding_service=FakeEmbeddingService()),
        execution_repository=PostgresExecutionRepository(),
        session_repository=PostgresSessionRepository(),
    )
    app.dependency_overrides[get_tool_executor_service] = lambda: executor
    yield downstream
    app.dependency_overrides.pop(get_tool_executor_service, None)


async def execute(async_client, server_id, tool_name: str, arguments: dict):
    return await async_client.post(f"/api/v1/servers/{server_id}/tools/{tool_name}/execute", json={"arguments": arguments})


async def test_success_returns_audited_duration(async_client, server, user_id):
    res = await execute(async_client, server.id, "add", {"a": 2, "b": 5})

    assert res.status_code == 200
    body = res.json()
    assert body["is_error"] is False
    assert body["structured_content"] == {"result": 7}
    record = await PostgresExecutionRepository().get_by_id(UUID(body["execution_id"]), user_id=user_id)
    assert record is not None
    assert record.duration_ms == body["duration_ms"]


async def test_tool_error_returns_200_with_is_error(async_client, server):
    res = await execute(async_client, server.id, "explode", {})

    assert res.status_code == 200
    assert res.json()["is_error"] is True


async def test_invalid_arguments_is_422_and_recorded_as_rejected(async_client, server, fake_executor, user_id):
    res = await execute(async_client, server.id, "add", {"a": 2})

    assert res.status_code == 422
    assert res.json()["error"]["details"]["reason"] == "invalid_arguments"
    assert fake_executor.calls == []
    items, total = await PostgresExecutionRepository().list(server_id=server.id, user_id=user_id)
    assert total == 1
    assert items[0].status == ToolCallStatus.REJECTED

    listed = await async_client.get("/api/v1/executions", params={"status": "rejected"})
    assert [item["status"] for item in listed.json()["items"]] == ["rejected"]
    not_listed = await async_client.get("/api/v1/executions", params={"status": "completed"})
    assert not_listed.json()["total"] == 0


async def test_unknown_tool_is_404_without_record(async_client, server, user_id):
    res = await execute(async_client, server.id, "nope", {})

    assert res.status_code == 404
    _, total = await PostgresExecutionRepository().list(user_id=user_id)
    assert total == 0


async def test_unknown_server_is_404(async_client):
    res = await execute(async_client, uuid4(), "add", {})

    assert res.status_code == 404


async def test_downstream_failure_is_502(async_client, server):
    res = await execute(async_client, server.id, "hang", {})

    assert res.status_code == 502
    assert "timed out" in res.json()["error"]["message"]


async def test_execution_history_outlives_its_server(async_client, other_user_client, server):
    """Deleting a Server keeps its Executions for the owner, still pointing at the deleted Server's id."""
    execution_id = (await execute(async_client, server.id, "add", {"a": 1, "b": 2})).json()["execution_id"]

    assert (await async_client.delete(f"/api/v1/servers/{server.id}")).status_code == 204

    detail = await async_client.get(f"/api/v1/executions/{execution_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["server_id"] == str(server.id)
    assert detail.json()["server_name"] == "Math Server"
    # The id is kept, but the Server itself is gone: the console shows it as deleted.
    assert (await async_client.get(f"/api/v1/servers/{server.id}")).status_code == 404
    listed = (await async_client.get("/api/v1/executions")).json()["items"]
    assert [item["id"] for item in listed] == [execution_id]

    # Still private to its owner.
    assert (await other_user_client.get(f"/api/v1/executions/{execution_id}")).status_code == 404
    assert (await other_user_client.get("/api/v1/executions")).json()["items"] == []
