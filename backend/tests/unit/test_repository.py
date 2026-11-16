"""Unit tests for repository implementations."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.core.enums.server_enum import ServerHealthStatus, TransportType
from app.domain.execution_entity import ExecutionEntity
from app.domain.server_entity import ServerEntity
from app.domain.tool_entity import ToolEntity
from app.infrastructure.repositories.execution_repository import PostgresExecutionRepository
from app.infrastructure.repositories.server_repository import PostgresServerRepository
from app.infrastructure.repositories.tool_repository import PostgresToolRepository
from app.schemas.connection_schema import StdioConfig


async def test_server_repository_crud(account_id):
    repo = PostgresServerRepository()
    server_id = uuid4()
    server = ServerEntity(
        id=server_id,
        name="test-server",
        description="Testing repository storage",
        transport=TransportType.STDIO,
        stdio_config=StdioConfig(command="python3", args=["test.py"]),
        enabled=True,
        health_status=ServerHealthStatus.UNKNOWN,
        user_id=account_id,
    )

    # 1. Create
    created = await repo.create(server)
    assert created.id == server_id
    assert created.name == "test-server"

    # 2. Get by ID
    fetched = await repo.get_by_id(server_id, user_id=account_id)
    assert fetched is not None
    assert fetched.name == "test-server"
    assert fetched.stdio_config is not None
    assert fetched.stdio_config.command == "python3"

    # 3. Get by Name
    fetched_by_name = await repo.get_by_name("TEST-SERVER", user_id=account_id)
    assert fetched_by_name is not None
    assert fetched_by_name.id == server_id

    # 4. List with filter
    items, total = await repo.list(search="test-server", enabled=True, user_id=account_id)
    assert total == 1
    assert len(items) == 1

    # 5. Update
    server.description = "Updated description"
    server.health_status = ServerHealthStatus.HEALTHY
    updated = await repo.update(server)
    assert updated.description == "Updated description"
    assert updated.health_status == ServerHealthStatus.HEALTHY

    # 6. Delete
    deleted = await repo.delete(server_id)
    assert deleted is True

    # 7. Verify deleted
    assert await repo.get_by_id(server_id, user_id=account_id) is None


async def test_tool_repository_crud_and_cascade(account_id):
    server_repo = PostgresServerRepository()
    tool_repo = PostgresToolRepository()
    server_id = uuid4()

    # Create server first (foreign key target)
    server = ServerEntity(
        id=server_id,
        name="parent-server",
        transport=TransportType.STDIO,
        user_id=account_id,
    )
    await server_repo.create(server)

    tool1 = ToolEntity(
        id=uuid4(),
        server_id=server_id,
        server_name="parent-server",
        name="echo",
        description="Echo text",
        input_schema={"type": "object"},
        availability_status="AVAILABLE",
        last_discovered_at=datetime.now(UTC),
        user_id=account_id,
    )
    tool2 = ToolEntity(
        id=uuid4(),
        server_id=server_id,
        server_name="parent-server",
        name="reverse",
        description="Reverse text",
        input_schema={"type": "object"},
        availability_status="AVAILABLE",
        last_discovered_at=datetime.now(UTC),
        user_id=account_id,
    )

    # 1. Save tools
    saved = await tool_repo.replace_server_tools(server_id, "parent-server", [tool1, tool2])
    assert len(saved) == 2

    # 2. Get tool
    fetched = await tool_repo.get_tool("echo", server_id=server_id, user_id=account_id)
    assert fetched is not None
    assert fetched.name == "echo"

    # 3. List tools
    items, total = await tool_repo.list_tools(server_id=server_id, user_id=account_id)
    assert total == 2
    assert len(items) == 2

    # 4. Search tools
    search_items, search_total = await tool_repo.list_tools(search="reverse", user_id=account_id)
    assert search_total == 1
    assert search_items[0].name == "reverse"

    # 5. Get tool by its id
    by_id = await tool_repo.get_tool(str(tool1.id), user_id=account_id)
    assert by_id is not None
    assert by_id.name == "echo"

    # 6. Re-discovery replaces the server's tools: old ids are gone, the new tools are stored as given
    rediscovered = [replace(tool1, id=uuid4(), description="Echo v2"), replace(tool2, id=uuid4(), name="upper")]
    await tool_repo.replace_server_tools(server_id, "parent-server", rediscovered)
    after, after_total = await tool_repo.list_tools(server_id=server_id, user_id=account_id)
    assert after_total == 2
    assert {t.id for t in after} == {t.id for t in rediscovered}
    assert await tool_repo.get_tool(str(tool1.id), user_id=account_id) is None
    assert (await tool_repo.get_tool(str(rediscovered[0].id), user_id=account_id)).description == "Echo v2"

    # 7. Cascade delete when parent server is deleted
    await server_repo.delete(server_id)
    _, remaining_total = await tool_repo.list_tools(server_id=server_id, user_id=account_id)
    assert remaining_total == 0


async def test_execution_repository_crud(account_id):
    server_repo = PostgresServerRepository()
    exec_repo = PostgresExecutionRepository()
    exec_id = uuid4()
    server_id = uuid4()

    # Create parent server for foreign key integrity
    server = ServerEntity(
        id=server_id,
        name="test-server",
        transport=TransportType.STDIO,
        user_id=account_id,
    )
    await server_repo.create(server)

    record = ExecutionEntity(
        id=exec_id,
        server_id=server_id,
        server_name="test-server",
        tool_name="add",
        arguments={"a": 1, "b": 2},
        is_error=False,
        duration_ms=12.5,
        executed_at=datetime.now(UTC),
        response={"content": [{"type": "text", "text": "3"}]},
    )

    # 1. Create
    created = await exec_repo.create(record)
    assert created.id == exec_id
    assert created.tool_name == "add"
    assert created.response == {"content": [{"type": "text", "text": "3"}]}

    # 2. Get by ID
    fetched = await exec_repo.get_by_id(exec_id, user_id=account_id)
    assert fetched is not None
    assert fetched.arguments == {"a": 1, "b": 2}
    assert fetched.response == {"content": [{"type": "text", "text": "3"}]}

    # 3. List
    items, total = await exec_repo.list(server_id=server_id, user_id=account_id)
    assert total == 1
    assert items[0].id == exec_id

    # Filter by recorded status
    await exec_repo.create(
        ExecutionEntity(
            id=uuid4(),
            server_id=server_id,
            server_name="test-server",
            tool_name="add",
            arguments={"a": "x"},
            is_error=True,
            duration_ms=0.0,
            executed_at=datetime.now(UTC),
            error_message="Invalid arguments",
            status="rejected",
        )
    )
    rejected, rejected_total = await exec_repo.list(status="rejected", user_id=account_id)
    assert rejected_total == 1
    assert rejected[0].status == "rejected"
    _, completed_total = await exec_repo.list(status="completed", user_id=account_id)
    assert completed_total == 1

    # Filter non-matching
    items_none, total_none = await exec_repo.list(tool_name="nonexistent", user_id=account_id)
    assert total_none == 0
    assert len(items_none) == 0
