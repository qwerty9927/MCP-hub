"""Unit tests for Session Explorer repository and service layers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.enums.server_enum import ServerHealthStatus, TransportType
from app.core.enums.session_enum import SessionStatus, ToolCallStatus
from app.core.exceptions import NotFoundError
from app.domain.execution_entity import ExecutionEntity
from app.domain.server_entity import ServerEntity
from app.domain.session_entity import SessionEntity
from app.infrastructure.repositories.execution_repo import PostgresExecutionRepository
from app.infrastructure.repositories.server_repo import PostgresServerRepository
from app.infrastructure.repositories.session_repo import PostgresSessionRepository
from app.schemas.session import SessionCreate
from app.services.session_explorer import SessionExplorerService, mask_sensitive_data


def test_mask_sensitive_data():
    """Verify recursive masking of sensitive keys."""
    raw = {
        "api_key": "secret123",
        "nested": {
            "token": "tok_abc",
            "safe_param": "hello world",
            "password": "p@ssword",
        },
        "items": [
            {"user": "alice", "credential": "cred_xyz"},
            {"auth_token": "bearer 123", "normal": 42},
        ],
    }
    masked = mask_sensitive_data(raw)
    assert masked["api_key"] == "***MASKED***"
    assert masked["nested"]["token"] == "***MASKED***"
    assert masked["nested"]["password"] == "***MASKED***"
    assert masked["nested"]["safe_param"] == "hello world"
    assert masked["items"][0]["credential"] == "***MASKED***"
    assert masked["items"][0]["user"] == "alice"
    assert masked["items"][1]["auth_token"] == "***MASKED***"
    assert masked["items"][1]["normal"] == 42


@pytest.mark.asyncio
async def test_session_repository_crud_and_metrics():
    """Verify session repository creation, metrics aggregation, search, and activity updates."""
    session_repo = PostgresSessionRepository()
    exec_repo = PostgresExecutionRepository()
    server_repo = PostgresServerRepository()

    # 1. Register a server to attach executions to
    server_id = uuid4()
    await server_repo.create(
        ServerEntity(
            id=server_id,
            name="demo-math",
            transport=TransportType.STDIO,
            health_status=ServerHealthStatus.HEALTHY,
        )
    )

    # 2. Create session
    session_id = uuid4().hex
    now = datetime.now(UTC)
    session = SessionEntity(
        id=session_id,
        title="Test Interactive Session",
        status=SessionStatus.ACTIVE,
        metadata={"client": "test_client"},
        created_at=now,
        last_activity_at=now,
    )
    created = await session_repo.create(session)
    assert created.id == session_id
    assert created.title == "Test Interactive Session"
    assert created.status == SessionStatus.ACTIVE

    # 3. Add executions: 2 successful, 1 failed
    exec_1_id = uuid4()
    await exec_repo.create(
        ExecutionEntity(
            id=exec_1_id,
            server_id=server_id,
            server_name="demo-math",
            tool_name="add",
            arguments={"a": 1, "b": 2},
            is_error=False,
            duration_ms=15.0,
            executed_at=now,
            session_id=session_id,
            status="completed",
        )
    )

    exec_2_id = uuid4()
    await exec_repo.create(
        ExecutionEntity(
            id=exec_2_id,
            server_id=server_id,
            server_name="demo-math",
            tool_name="multiply",
            arguments={"a": 3, "b": 4},
            is_error=False,
            duration_ms=20.0,
            executed_at=now,
            session_id=session_id,
            status="completed",
        )
    )

    exec_3_id = uuid4()
    await exec_repo.create(
        ExecutionEntity(
            id=exec_3_id,
            server_id=server_id,
            server_name="demo-math",
            tool_name="divide",
            arguments={"a": 10, "b": 0},
            is_error=True,
            duration_ms=5.0,
            executed_at=now,
            error_message="Division by zero",
            session_id=session_id,
            status="failed",
        )
    )

    # 4. Get by ID and verify aggregated metrics
    detail = await session_repo.get_by_id(session_id)
    assert detail is not None
    assert detail.id == session_id
    assert detail.total_tool_calls == 3
    assert detail.successful_tool_calls == 2
    assert detail.failed_tool_calls == 1

    # 5. List sessions
    items, total = await session_repo.list(search="Interactive", status="active")
    assert total >= 1
    matched = [s for s in items if s.id == session_id]
    assert len(matched) == 1
    assert matched[0].total_tool_calls == 3

    # 6. Update status
    updated = await session_repo.update_status(session_id, "completed")
    assert updated is True
    detail_after = await session_repo.get_by_id(session_id)
    assert detail_after.status == SessionStatus.COMPLETED


@pytest.mark.asyncio
async def test_execution_repo_list_by_session_sorting_and_filtering():
    """Verify tool call chronological sorting, direction, and filtering."""
    session_repo = PostgresSessionRepository()
    exec_repo = PostgresExecutionRepository()
    server_repo = PostgresServerRepository()

    server_id = uuid4()
    await server_repo.create(
        ServerEntity(
            id=server_id,
            name="sorting-server",
            transport=TransportType.STDIO,
            health_status=ServerHealthStatus.HEALTHY,
        )
    )

    session_id = uuid4().hex
    await session_repo.get_or_create(session_id, title="Sorting Test")

    # Add 3 tool calls at sequential timestamps
    t1 = datetime(2026, 11, 8, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 11, 8, 10, 1, 0, tzinfo=UTC)
    t3 = datetime(2026, 11, 8, 10, 2, 0, tzinfo=UTC)

    await exec_repo.create(
        ExecutionEntity(
            id=uuid4(),
            server_id=server_id,
            server_name="sorting-server",
            tool_name="first_call",
            arguments={},
            is_error=False,
            duration_ms=10.0,
            executed_at=t1,
            started_at=t1,
            session_id=session_id,
            status="completed",
        )
    )
    await exec_repo.create(
        ExecutionEntity(
            id=uuid4(),
            server_id=server_id,
            server_name="sorting-server",
            tool_name="second_call",
            arguments={},
            is_error=True,
            duration_ms=25.0,
            executed_at=t2,
            started_at=t2,
            session_id=session_id,
            status="failed",
        )
    )
    await exec_repo.create(
        ExecutionEntity(
            id=uuid4(),
            server_id=server_id,
            server_name="sorting-server",
            tool_name="third_call",
            arguments={},
            is_error=False,
            duration_ms=15.0,
            executed_at=t3,
            started_at=t3,
            session_id=session_id,
            status="completed",
        )
    )

    # Ascending order (default - oldest first)
    calls_asc, count_asc = await exec_repo.list_by_session(session_id=session_id, order="asc")
    assert count_asc == 3
    assert [c.tool_name for c in calls_asc] == [
        "first_call",
        "second_call",
        "third_call",
    ]

    # Descending order (newest first)
    calls_desc, count_desc = await exec_repo.list_by_session(session_id=session_id, order="desc")
    assert count_desc == 3
    assert [c.tool_name for c in calls_desc] == [
        "third_call",
        "second_call",
        "first_call",
    ]

    # Filter by status: failed
    calls_failed, count_failed = await exec_repo.list_by_session(
        session_id=session_id, status="failed"
    )
    assert count_failed == 1
    assert calls_failed[0].tool_name == "second_call"
    assert calls_failed[0].status == ToolCallStatus.FAILED

    # Filter by tool_name
    calls_name, _ = await exec_repo.list_by_session(session_id=session_id, tool_name="third")
    assert len(calls_name) == 1
    assert calls_name[0].tool_name == "third_call"


@pytest.mark.asyncio
async def test_session_explorer_service_errors():
    """Verify service raises NotFoundError when querying nonexistent session or tool call."""
    session_repo = PostgresSessionRepository()
    exec_repo = PostgresExecutionRepository()
    service = SessionExplorerService(session_repo, exec_repo)

    # Missing session
    fake_session_id = uuid4().hex
    with pytest.raises(NotFoundError):
        await service.get_session(fake_session_id)

    with pytest.raises(NotFoundError):
        await service.list_session_tool_calls(fake_session_id)

    # Create session, but query missing tool call
    session_resp = await service.create_session(SessionCreate(title="Empty Session"))
    fake_call_id = uuid4()
    with pytest.raises(NotFoundError):
        await service.get_session_tool_call(session_resp.id, fake_call_id)
