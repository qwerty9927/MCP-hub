"""Unit tests for ToolCatalogService."""

from uuid import uuid4

import mcp.types as mcp_types
import pytest

from app.core.exceptions import NotFoundError
from app.domain.server import ServerEntity
from app.schemas.server import TransportType
from app.services.connection_manager import ConnectionManager
from app.services.tool_catalog import ToolCatalogService


class MockConnectionManager(ConnectionManager):
    """Mock ConnectionManager returning fixed tools."""

    async def list_tools(
        self, server: ServerEntity, timeout: float | None = None
    ) -> list[mcp_types.Tool]:
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
    return ToolCatalogService()


async def test_refresh_and_list_tools(catalog_service: ToolCatalogService):
    server = ServerEntity(
        id=uuid4(),
        name="server-alpha",
        transport=TransportType.STDIO,
    )
    mock_mgr = MockConnectionManager()

    tools = await catalog_service.refresh_server_tools(server, mock_mgr)
    assert len(tools) == 2
    assert tools[0].name == "tool_a"

    # Verify qualified IDs handle collisions
    assert tools[0].id == f"{server.id}:tool_a"

    # List all
    res = await catalog_service.list_tools()
    assert res.total == 2
    assert len(res.items) == 2

    # Filter by tool_name
    res_filtered = await catalog_service.list_tools(tool_name="tool_a")
    assert res_filtered.total == 1
    assert res_filtered.items[0].name == "tool_a"


async def test_duplicate_tool_names_across_servers(catalog_service: ToolCatalogService):
    """Duplicate tool names on different servers should have distinct qualified IDs."""
    server1 = ServerEntity(id=uuid4(), name="server-1", transport=TransportType.STDIO)
    server2 = ServerEntity(id=uuid4(), name="server-2", transport=TransportType.STDIO)
    mock_mgr = MockConnectionManager()

    await catalog_service.refresh_server_tools(server1, mock_mgr)
    await catalog_service.refresh_server_tools(server2, mock_mgr)

    res = await catalog_service.list_tools()
    assert res.total == 4

    tool1 = await catalog_service.get_tool(f"{server1.id}:tool_a")
    assert tool1.server_id == server1.id

    tool2 = await catalog_service.get_tool(f"{server2.id}:tool_a")
    assert tool2.server_id == server2.id


async def test_get_tool_not_found(catalog_service: ToolCatalogService):
    with pytest.raises(NotFoundError):
        await catalog_service.get_tool("nonexistent_tool")
