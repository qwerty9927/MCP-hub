"""Unit tests for ToolCatalogService."""

from uuid import uuid4

import mcp.types as mcp_types
import pytest

from app.core.enums.server_enum import TransportType
from app.core.exceptions import NotFoundError
from app.domain.server_entity import ServerEntity
from app.infrastructure.repositories.server_repository import PostgresServerRepository
from app.infrastructure.repositories.tool_repository import PostgresToolRepository
from app.services.connection_manager import ConnectionManager
from app.services.tool_catalog import ToolCatalogService
from tests.fake_embeddings import FakeEmbeddingService


class MockConnectionManager(ConnectionManager):
    """Mock ConnectionManager returning fixed tools."""

    async def list_tools(self, server: ServerEntity, timeout: float | None = None) -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name="tool_a",
                description="Tool A description",
                input_schema={"type": "object", "properties": {"x": {"type": "integer"}}},
            ),
            mcp_types.Tool(
                name="tool_b",
                description="Tool B description",
                input_schema={"type": "object"},
            ),
        ]


@pytest.fixture
def catalog_service() -> ToolCatalogService:
    return ToolCatalogService(tool_repository=PostgresToolRepository(), embedding_service=FakeEmbeddingService())


async def stored_server(name: str, account_id) -> ServerEntity:
    return await PostgresServerRepository().create(ServerEntity(id=uuid4(), name=name, transport=TransportType.STDIO, user_id=account_id))


async def test_refresh_and_list_tools(catalog_service: ToolCatalogService, account_id):
    server = await stored_server("server-alpha", account_id=account_id)
    mock_mgr = MockConnectionManager()

    tools = await catalog_service.refresh_server_tools(server, mock_mgr)
    assert len(tools) == 2
    assert tools[0].name == "tool_a"

    # Refreshing replaces the tools, so each gets a new UUID id
    again = await catalog_service.refresh_server_tools(server, mock_mgr)
    assert {t.id for t in again}.isdisjoint({t.id for t in tools})

    # List all
    res = await catalog_service.list_tools(user_id=account_id)
    assert res.total == 2
    assert len(res.items) == 2

    # Filter by tool_name
    res_filtered = await catalog_service.list_tools(tool_name="tool_a", user_id=account_id)
    assert res_filtered.total == 1
    assert res_filtered.items[0].name == "tool_a"


async def test_duplicate_tool_names_across_servers(catalog_service: ToolCatalogService, account_id):
    """Duplicate tool names on different servers are distinct Tools, told apart by server."""
    server1 = await stored_server("server-1", account_id=account_id)
    server2 = await stored_server("server-2", account_id=account_id)
    mock_mgr = MockConnectionManager()

    await catalog_service.refresh_server_tools(server1, mock_mgr)
    await catalog_service.refresh_server_tools(server2, mock_mgr)

    res = await catalog_service.list_tools(user_id=account_id)
    assert res.total == 4

    tool1 = await catalog_service.get_tool("tool_a", server_id=server1.id, user_id=account_id)
    assert tool1.server_id == server1.id

    tool2 = await catalog_service.get_tool("tool_a", server_id=server2.id, user_id=account_id)
    assert tool2.server_id == server2.id


async def test_reads_reflect_the_database_without_a_restart(catalog_service: ToolCatalogService, account_id):
    """Tools written by another service instance are visible immediately: nothing is cached in memory."""
    server = await stored_server("server-shared", account_id=account_id)
    await ToolCatalogService(tool_repository=PostgresToolRepository(), embedding_service=FakeEmbeddingService()).refresh_server_tools(
        server, MockConnectionManager()
    )

    assert (await catalog_service.get_tool("tool_a", server_id=server.id, user_id=account_id)).name == "tool_a"

    await ToolCatalogService(tool_repository=PostgresToolRepository(), embedding_service=FakeEmbeddingService()).remove_server_tools(
        server.id
    )

    with pytest.raises(NotFoundError):
        await catalog_service.get_tool("tool_a", server_id=server.id, user_id=account_id)


async def test_get_tool_not_found(catalog_service: ToolCatalogService, account_id):
    with pytest.raises(NotFoundError):
        await catalog_service.get_tool("nonexistent_tool", user_id=account_id)
