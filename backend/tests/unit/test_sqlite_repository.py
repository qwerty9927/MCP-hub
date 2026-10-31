"""Unit tests for SQLite repository implementations."""

from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities import ExecutionEntity, ServerEntity, ToolEntity
from app.infrastructure.repositories.sqlite import (
    SqliteExecutionRepository,
    SqliteServerRepository,
    SqliteToolRepository,
)
from app.schemas.server import ServerHealthStatus, StdioConfig, TransportType


async def test_sqlite_server_repository_crud():
    repo = SqliteServerRepository()
    server_id = uuid4()
    server = ServerEntity(
        id=server_id,
        name="sqlite-test-server",
        description="Testing SQLite storage",
        transport=TransportType.STDIO,
        stdio_config=StdioConfig(command="python3", args=["test.py"]),
        enabled=True,
        health_status=ServerHealthStatus.UNKNOWN,
    )

    # 1. Create
    created = await repo.create(server)
    assert created.id == server_id
    assert created.name == "sqlite-test-server"

    # 2. Get by ID
    fetched = await repo.get_by_id(server_id)
    assert fetched is not None
    assert fetched.name == "sqlite-test-server"
    assert fetched.stdio_config is not None
    assert fetched.stdio_config.command == "python3"

    # 3. Get by Name
    fetched_by_name = await repo.get_by_name("SQLITE-TEST-SERVER")
    assert fetched_by_name is not None
    assert fetched_by_name.id == server_id

    # 4. List with filter
    items, total = await repo.list(search="sqlite-test", enabled=True)
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
    assert await repo.get_by_id(server_id) is None


async def test_sqlite_tool_repository_crud_and_cascade():
    server_repo = SqliteServerRepository()
    tool_repo = SqliteToolRepository()
    server_id = uuid4()

    # Create server first (foreign key target)
    server = ServerEntity(
        id=server_id,
        name="parent-server",
        transport=TransportType.STDIO,
    )
    await server_repo.create(server)

    tool1 = ToolEntity(
        id=f"{server_id}:echo",
        server_id=server_id,
        server_name="parent-server",
        name="echo",
        description="Echo text",
        input_schema={"type": "object"},
        availability_status="AVAILABLE",
        last_discovered_at=datetime.now(UTC),
    )
    tool2 = ToolEntity(
        id=f"{server_id}:reverse",
        server_id=server_id,
        server_name="parent-server",
        name="reverse",
        description="Reverse text",
        input_schema={"type": "object"},
        availability_status="AVAILABLE",
        last_discovered_at=datetime.now(UTC),
    )

    # 1. Save tools
    saved = await tool_repo.save_server_tools(server_id, "parent-server", [tool1, tool2])
    assert len(saved) == 2

    # 2. Get tool
    fetched = await tool_repo.get_tool("echo", server_id=server_id)
    assert fetched is not None
    assert fetched.name == "echo"

    # 3. List tools
    items, total = await tool_repo.list_tools(server_id=server_id)
    assert total == 2
    assert len(items) == 2

    # 4. Search tools
    search_items, search_total = await tool_repo.list_tools(search="reverse")
    assert search_total == 1
    assert search_items[0].name == "reverse"

    # 5. Load all tools
    all_tools = await tool_repo.load_all_tools()
    assert len(all_tools) >= 2

    # 6. Cascade delete when parent server is deleted
    await server_repo.delete(server_id)
    remaining_tools, remaining_total = await tool_repo.list_tools(server_id=server_id)
    assert remaining_total == 0


async def test_sqlite_execution_repository_crud():
    server_repo = SqliteServerRepository()
    exec_repo = SqliteExecutionRepository()
    exec_id = uuid4()
    server_id = uuid4()

    # Create parent server for foreign key integrity
    server = ServerEntity(
        id=server_id,
        name="test-server",
        transport=TransportType.STDIO,
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
    )

    # 1. Create
    created = await exec_repo.create(record)
    assert created.id == exec_id
    assert created.tool_name == "add"

    # 2. Get by ID
    fetched = await exec_repo.get_by_id(exec_id)
    assert fetched is not None
    assert fetched.arguments == {"a": 1, "b": 2}

    # 3. List
    items, total = await exec_repo.list(server_id=server_id)
    assert total == 1
    assert items[0].id == exec_id

    # Filter non-matching
    items_none, total_none = await exec_repo.list(tool_name="nonexistent")
    assert total_none == 0
    assert len(items_none) == 0
