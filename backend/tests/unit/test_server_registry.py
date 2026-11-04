"""Unit tests for ServerRegistryService."""

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.infrastructure.repositories.server_repo import InMemoryServerRepository
from app.schemas.server import (
    ServerCreate,
    ServerHealthStatus,
    ServerUpdate,
    StdioConfig,
    TransportType,
)
from app.services.server_registry import ServerRegistryService


@pytest.fixture
def registry_service() -> ServerRegistryService:
    repo = InMemoryServerRepository()
    return ServerRegistryService(repository=repo)


async def test_create_server_success(registry_service: ServerRegistryService):
    payload = ServerCreate(
        name="test-server-1",
        description="A test MCP server",
        transport=TransportType.STDIO,
        stdio_config=StdioConfig(command="python3", args=["server.py"]),
    )
    server = await registry_service.create_server(payload)
    assert server.name == "test-server-1"
    assert server.transport == TransportType.STDIO
    assert server.health_status == ServerHealthStatus.UNKNOWN
    assert server.enabled is True
    assert server.connection_config.command == "python3"


async def test_create_server_duplicate_name(registry_service: ServerRegistryService):
    payload = ServerCreate(
        name="duplicate-server",
        transport=TransportType.STDIO,
        stdio_config=StdioConfig(command="python3", args=["server.py"]),
    )
    await registry_service.create_server(payload)

    # Attempt duplicate creation
    with pytest.raises(ConflictError):
        await registry_service.create_server(payload)


async def test_get_server_not_found(registry_service: ServerRegistryService):
    from uuid import uuid4

    with pytest.raises(NotFoundError):
        await registry_service.get_server(uuid4())


async def test_update_server(registry_service: ServerRegistryService):
    payload = ServerCreate(
        name="initial-name",
        description="Initial description",
        transport=TransportType.STDIO,
        stdio_config=StdioConfig(command="python3", args=["server.py"]),
    )
    server = await registry_service.create_server(payload)

    updated = await registry_service.update_server(
        server.id,
        ServerUpdate(name="updated-name", description="Updated description", enabled=False),
    )
    assert updated.name == "updated-name"
    assert updated.description == "Updated description"
    assert updated.enabled is False


async def test_list_servers_filtering_and_pagination(registry_service: ServerRegistryService):
    for i in range(5):
        await registry_service.create_server(
            ServerCreate(
                name=f"server-{i}",
                transport=TransportType.STDIO,
                stdio_config=StdioConfig(command="python3"),
                enabled=(i % 2 == 0),
            )
        )

    # Filter enabled
    res_enabled = await registry_service.list_servers(enabled=True)
    assert res_enabled.total == 3
    assert len(res_enabled.items) == 3

    # Pagination
    res_paged = await registry_service.list_servers(page=1, page_size=2)
    assert len(res_paged.items) == 2
    assert res_paged.total == 5
    assert res_paged.total_pages == 3


async def test_delete_server(registry_service: ServerRegistryService):
    payload = ServerCreate(
        name="to-delete",
        transport=TransportType.STDIO,
        stdio_config=StdioConfig(command="python3"),
    )
    server = await registry_service.create_server(payload)
    success = await registry_service.delete_server(server.id)
    assert success is True

    with pytest.raises(NotFoundError):
        await registry_service.get_server(server.id)
