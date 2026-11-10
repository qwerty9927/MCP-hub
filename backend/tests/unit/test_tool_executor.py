"""Tests for the Execution module (ToolExecutor), exercised only through its `execute` interface.

Real PostgreSQL repositories stand behind the module; only the downstream MCP Server is faked,
at the `ConnectionManager` seam.
"""

import asyncio
from uuid import uuid4

import pytest

from app.core.enums.execution_enum import ExecutionOutcomeKind, RejectionReason
from app.core.enums.server_enum import TransportType
from app.core.enums.session_enum import ToolCallStatus
from app.domain.execution_entity import ExecutionEntity
from app.domain.server_entity import ServerEntity
from app.infrastructure.repositories.execution_repository import PostgresExecutionRepository
from app.infrastructure.repositories.server_repository import PostgresServerRepository
from app.infrastructure.repositories.session_repository import PostgresSessionRepository
from app.infrastructure.repositories.tool_repository import PostgresToolRepository
from app.schemas.connection_schema import StdioConfig
from app.services.server_registry import ServerRegistryService
from app.services.tool_catalog import ToolCatalogService
from app.services.tool_executor import ToolExecutor
from tests.fake_downstream import FakeDownstream


class FailingExecutionRepository(PostgresExecutionRepository):
    async def create(self, execution: ExecutionEntity) -> ExecutionEntity:
        raise RuntimeError("database unavailable")


@pytest.fixture
def server_repo() -> PostgresServerRepository:
    return PostgresServerRepository()


@pytest.fixture
def execution_repo() -> PostgresExecutionRepository:
    return PostgresExecutionRepository()


@pytest.fixture
def session_repo() -> PostgresSessionRepository:
    return PostgresSessionRepository()


@pytest.fixture
def downstream() -> FakeDownstream:
    return FakeDownstream()


@pytest.fixture
def catalog() -> ToolCatalogService:
    return ToolCatalogService(repository=PostgresToolRepository())


def build_executor(
    server_repo: PostgresServerRepository,
    downstream: FakeDownstream,
    catalog: ToolCatalogService,
    execution_repo: PostgresExecutionRepository,
    session_repo: PostgresSessionRepository,
) -> ToolExecutor:
    return ToolExecutor(
        server_registry=ServerRegistryService(repository=server_repo),
        connection_manager=downstream,
        tool_catalog=catalog,
        execution_repository=execution_repo,
        session_repository=session_repo,
    )


@pytest.fixture
def executor(server_repo, downstream, catalog, execution_repo, session_repo) -> ToolExecutor:
    return build_executor(server_repo, downstream, catalog, execution_repo, session_repo)


async def register_server(server_repo, name: str = "Math Server", enabled: bool = True) -> ServerEntity:
    server = ServerEntity(
        name=name,
        transport=TransportType.STDIO,
        stdio_config=StdioConfig(command="python3"),
        enabled=enabled,
    )
    return await server_repo.create(server)


@pytest.fixture
async def connected_server(server_repo, catalog, downstream) -> ServerEntity:
    server = await register_server(server_repo)
    await catalog.refresh_server_tools(server, downstream)
    return server


async def only_execution(execution_repo, server: ServerEntity) -> ExecutionEntity:
    items, total = await execution_repo.list(server_id=server.id)
    assert total == 1
    return items[0]


# --- Succeeded -------------------------------------------------------------------------------


async def test_tool_slug_succeeds_and_is_recorded_once(executor, execution_repo, connected_server):
    outcome = await executor.execute("math_server__add", {"a": 2, "b": 3})

    assert outcome.kind == ExecutionOutcomeKind.SUCCEEDED
    assert outcome.rejection_reason is None
    assert outcome.content == [{"type": "text", "text": "5"}]
    assert outcome.structured_content == {"result": 5}
    assert outcome.error_message is None
    assert outcome.server_id == connected_server.id
    assert outcome.tool_name == "add"

    record = await only_execution(execution_repo, connected_server)
    assert record.id == outcome.execution_id
    assert record.status == ToolCallStatus.COMPLETED
    assert record.is_error is False
    assert record.duration_ms == outcome.duration_ms


async def test_qualified_tool_id_succeeds(executor, connected_server):
    outcome = await executor.execute(f"{connected_server.id}:add", {"a": 1, "b": 1})

    assert outcome.kind == ExecutionOutcomeKind.SUCCEEDED
    assert outcome.structured_content == {"result": 2}


async def test_qualified_tool_id_refreshes_catalog_on_miss(executor, server_repo, downstream):
    server = await register_server(server_repo)  # never refreshed: catalog is empty

    outcome = await executor.execute(f"{server.id}:add", {"a": 4, "b": 4})

    assert outcome.kind == ExecutionOutcomeKind.SUCCEEDED
    assert outcome.structured_content == {"result": 8}


# --- Tool Error / Failed ---------------------------------------------------------------------


async def test_tool_error_joins_text_blocks_and_records_failed(executor, execution_repo, connected_server):
    outcome = await executor.execute("math_server__explode", {})

    assert outcome.kind == ExecutionOutcomeKind.TOOL_ERROR
    assert outcome.error_message == "first line\nsecond line"
    record = await only_execution(execution_repo, connected_server)
    assert record.status == ToolCallStatus.FAILED
    assert record.is_error is True
    assert record.error_message == "first line\nsecond line"


async def test_tool_error_without_text_uses_fallback_message(executor, connected_server):
    outcome = await executor.execute("math_server__silent_error", {})

    assert outcome.kind == ExecutionOutcomeKind.TOOL_ERROR
    assert outcome.error_message == "Tool execution reported an error"


async def test_downstream_fault_is_failed_and_recorded(executor, execution_repo, connected_server):
    outcome = await executor.execute("math_server__hang", {})

    assert outcome.kind == ExecutionOutcomeKind.FAILED
    assert "timed out" in (outcome.error_message or "")
    record = await only_execution(execution_repo, connected_server)
    assert record.status == ToolCallStatus.FAILED
    assert record.is_error is True


async def test_cancellation_is_recorded_then_propagated(executor, execution_repo, connected_server):
    with pytest.raises(asyncio.CancelledError):
        await executor.execute("math_server__cancel", {})

    record = await only_execution(execution_repo, connected_server)
    assert record.status == ToolCallStatus.FAILED
    assert record.error_message == "cancelled"


# --- Rejected (recorded, downstream never contacted) -----------------------------------------


async def test_invalid_arguments_rejected_and_recorded(executor, execution_repo, downstream, connected_server):
    outcome = await executor.execute("math_server__add", {"a": 1})

    assert outcome.kind == ExecutionOutcomeKind.REJECTED
    assert outcome.rejection_reason == RejectionReason.INVALID_ARGUMENTS
    assert "'b' is a required property" in (outcome.error_message or "")
    assert outcome.duration_ms == 0
    assert downstream.calls == []

    record = await only_execution(execution_repo, connected_server)
    assert record.id == outcome.execution_id
    assert record.status == ToolCallStatus.REJECTED
    assert record.duration_ms == 0
    assert record.arguments == {"a": 1}


async def test_disabled_server_rejected_and_recorded(executor, server_repo, execution_repo, downstream, connected_server):
    connected_server.enabled = False
    await server_repo.update(connected_server)

    outcome = await executor.execute("math_server__add", {"a": 1, "b": 2})

    assert outcome.kind == ExecutionOutcomeKind.REJECTED
    assert outcome.rejection_reason == RejectionReason.SERVER_DISABLED
    assert "disabled" in (outcome.error_message or "").lower()
    assert downstream.calls == []
    record = await only_execution(execution_repo, connected_server)
    assert record.status == ToolCallStatus.REJECTED


async def test_unavailable_tool_rejected_and_recorded(executor, catalog, execution_repo, downstream, connected_server):
    tool = await catalog.get_tool("add", server_id=connected_server.id)
    tool.availability_status = "UNAVAILABLE"

    outcome = await executor.execute("math_server__add", {"a": 1, "b": 2})

    assert outcome.kind == ExecutionOutcomeKind.REJECTED
    assert outcome.rejection_reason == RejectionReason.TOOL_UNAVAILABLE
    assert downstream.calls == []
    record = await only_execution(execution_repo, connected_server)
    assert record.status == ToolCallStatus.REJECTED


# --- Unknown Tool Reference: not an Execution (ADR-0002) -------------------------------------


async def test_unknown_tool_is_rejected_without_execution_record(executor, execution_repo, session_repo, connected_server):
    session = await session_repo.get_or_create(session_id=f"sess-{uuid4()}")
    before = session.last_activity_at

    outcome = await executor.execute("math_server__does_not_exist", {}, session_id=session.id)

    assert outcome.kind == ExecutionOutcomeKind.REJECTED
    assert outcome.rejection_reason == RejectionReason.UNKNOWN_TOOL
    assert outcome.execution_id is None
    assert "math_server__does_not_exist" in (outcome.error_message or "")
    _, total = await execution_repo.list()
    assert total == 0
    detail = await session_repo.get_by_id(session.id)
    assert detail is not None
    assert detail.last_activity_at >= before


async def test_qualified_id_for_unregistered_server_is_unknown_tool(executor):
    outcome = await executor.execute(f"{uuid4()}:add", {"a": 1, "b": 2})

    assert outcome.kind == ExecutionOutcomeKind.REJECTED
    assert outcome.rejection_reason == RejectionReason.UNKNOWN_TOOL


# --- Session & audit robustness --------------------------------------------------------------


async def test_execution_is_linked_to_session_and_bumps_activity(executor, execution_repo, session_repo, connected_server):
    session = await session_repo.get_or_create(session_id=f"sess-{uuid4()}")

    outcome = await executor.execute("math_server__add", {"a": 1, "b": 2}, session_id=session.id)

    record = await only_execution(execution_repo, connected_server)
    assert record.session_id == session.id
    detail = await session_repo.get_by_id(session.id)
    assert detail is not None
    assert detail.total_tool_calls == 1
    assert detail.last_activity_at >= session.last_activity_at
    assert outcome.kind == ExecutionOutcomeKind.SUCCEEDED


async def test_audit_failure_still_returns_real_outcome(server_repo, downstream, catalog, session_repo, connected_server):
    executor = build_executor(server_repo, downstream, catalog, FailingExecutionRepository(), session_repo)

    outcome = await executor.execute("math_server__add", {"a": 2, "b": 2})

    assert outcome.kind == ExecutionOutcomeKind.SUCCEEDED
    assert outcome.structured_content == {"result": 4}
    assert len(downstream.calls) == 1


async def test_qualified_id_on_disabled_uncatalogued_server_is_server_disabled_without_record(
    executor, server_repo, execution_repo, downstream
):
    server = await register_server(server_repo, enabled=False)  # catalog empty, cannot refresh a disabled Server

    outcome = await executor.execute(f"{server.id}:add", {"a": 1, "b": 2})

    assert outcome.kind == ExecutionOutcomeKind.REJECTED
    assert outcome.rejection_reason == RejectionReason.SERVER_DISABLED
    assert outcome.execution_id is None
    assert downstream.calls == []
    _, total = await execution_repo.list()
    assert total == 0
