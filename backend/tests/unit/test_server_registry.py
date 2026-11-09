"""Unit tests for ServerRegistryService."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.enums.server_enum import ServerHealthStatus, TransportType
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.server_entity import ServerEntity
from app.infrastructure.repositories.server_repo import ServerRepositoryAbstract
from app.schemas.connection import StdioConfig
from app.schemas.server import (
    ServerCreate,
    ServerUpdate,
)
from app.services.server_registry import ServerRegistryService


@pytest.fixture
def mock_server_repo() -> AsyncMock:
    repo = AsyncMock(spec=ServerRepositoryAbstract)
    repo.create.side_effect = lambda s: s
    repo.update.side_effect = lambda s: s
    return repo


@pytest.fixture
def registry_service(mock_server_repo: AsyncMock) -> ServerRegistryService:
    return ServerRegistryService(repository=mock_server_repo)


async def test_create_server_success(registry_service: ServerRegistryService, mock_server_repo: AsyncMock):
    mock_server_repo.get_by_name.return_value = None
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
    mock_server_repo.get_by_name.assert_awaited_once_with("test-server-1")
    mock_server_repo.create.assert_awaited_once()


async def test_create_server_duplicate_name(registry_service: ServerRegistryService, mock_server_repo: AsyncMock):
    mock_server_repo.get_by_name.return_value = ServerEntity(
        name="duplicate-server",
        transport=TransportType.STDIO,
    )
    payload = ServerCreate(
        name="duplicate-server",
        transport=TransportType.STDIO,
        stdio_config=StdioConfig(command="python3", args=["server.py"]),
    )

    with pytest.raises(ConflictError):
        await registry_service.create_server(payload)

    mock_server_repo.create.assert_not_called()


async def test_get_server_not_found(registry_service: ServerRegistryService, mock_server_repo: AsyncMock):
    mock_server_repo.get_by_id.return_value = None

    with pytest.raises(NotFoundError):
        await registry_service.get_server(uuid4())


async def test_update_server(registry_service: ServerRegistryService, mock_server_repo: AsyncMock):
    server_id = uuid4()
    existing = ServerEntity(
        id=server_id,
        name="initial-name",
        description="Initial description",
        transport=TransportType.STDIO,
        stdio_config=StdioConfig(command="python3", args=["server.py"]),
        enabled=True,
    )
    mock_server_repo.get_by_id.return_value = existing
    mock_server_repo.get_by_name.return_value = None

    updated = await registry_service.update_server(
        server_id,
        ServerUpdate(name="updated-name", description="Updated description", enabled=False),
    )

    assert updated.name == "updated-name"
    assert updated.description == "Updated description"
    assert updated.enabled is False
    mock_server_repo.update.assert_awaited_once()


async def test_list_servers_filtering_and_pagination(registry_service: ServerRegistryService, mock_server_repo: AsyncMock):
    items = [
        ServerEntity(
            id=uuid4(),
            name=f"server-{i}",
            transport=TransportType.STDIO,
            enabled=(i % 2 == 0),
        )
        for i in range(5)
    ]
    mock_server_repo.list.return_value = (items, 5)

    res = await registry_service.list_servers(page=1, page_size=2, enabled=True)

    assert res.total == 5
    assert len(res.items) == 5
    assert res.total_pages == 3
    mock_server_repo.list.assert_awaited_once_with(
        page=1,
        page_size=2,
        enabled=True,
        transport=None,
        health_status=None,
        search=None,
        sort_by="created_at",
        sort_order="desc",
    )


async def test_delete_server(registry_service: ServerRegistryService, mock_server_repo: AsyncMock):
    server_id = uuid4()
    existing = ServerEntity(id=server_id, name="to-delete", transport=TransportType.STDIO)
    mock_server_repo.get_by_id.return_value = existing
    mock_server_repo.delete.return_value = True

    success = await registry_service.delete_server(server_id)
    assert success is True
    mock_server_repo.delete.assert_awaited_once_with(server_id)

    mock_server_repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await registry_service.delete_server(server_id)
