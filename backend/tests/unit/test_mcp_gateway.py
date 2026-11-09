"""Unit tests for MCP Gateway service."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import mcp.types as types
import pytest

from app.core.constants.meta_tools import (
    MULTI_EXECUTE_TOOLS_NAME,
    SEARCH_TOOLS_NAME,
)
from app.core.enums.server_enum import ServerHealthStatus, TransportType
from app.core.exceptions import ValidationError
from app.domain.server_entity import ServerEntity
from app.helpers.text import slugify
from app.mcp.multi_execute_tools import MULTI_EXECUTE_TOOLS_SCHEMA
from app.mcp.search_tools import SEARCH_TOOLS_SCHEMA
from app.schemas.common import PaginatedResponse
from app.schemas.server import ServerResponse
from app.schemas.tool import ToolResponse
from app.services.mcp_gateway import GatewayToolMapping, MCPGatewayService


@pytest.fixture
def mock_registry():
    return AsyncMock()


@pytest.fixture
def mock_tool_catalog():
    return AsyncMock()


@pytest.fixture
def mock_connection_mgr():
    return AsyncMock()


@pytest.fixture
def mock_tool_router():
    return AsyncMock()


@pytest.fixture
def gateway_service(mock_registry, mock_tool_catalog, mock_connection_mgr, mock_tool_router):
    return MCPGatewayService(
        server_registry=mock_registry,
        tool_catalog=mock_tool_catalog,
        connection_manager=mock_connection_mgr,
        tool_router=mock_tool_router,
    )


def test_slugify_name():
    assert slugify("Github Tools") == "github_tools"
    assert slugify("Postgres-DB #1") == "postgres_db_1"
    assert slugify("  --- special ---  ") == "special"
    assert slugify("!!!") == "server"


@pytest.mark.asyncio
async def test_refresh_tool_mappings_aggregation(gateway_service, mock_registry, mock_tool_catalog):
    server1_id = uuid4()
    server2_id = uuid4()
    now = datetime.now(UTC)

    mock_registry.list_servers.return_value = PaginatedResponse[ServerResponse](
        items=[
            ServerResponse(
                id=server1_id,
                name="Math Server",
                transport=TransportType.STDIO,
                connection_config={"command": "python"},
                enabled=True,
                health_status=ServerHealthStatus.HEALTHY,
                created_at=now,
                updated_at=now,
            ),
            ServerResponse(
                id=server2_id,
                name="Text Server",
                transport=TransportType.STDIO,
                connection_config={"command": "python"},
                enabled=True,
                health_status=ServerHealthStatus.HEALTHY,
                created_at=now,
                updated_at=now,
            ),
            ServerResponse(
                id=uuid4(),
                name="Disabled Server",
                transport=TransportType.STDIO,
                connection_config={"command": "python"},
                enabled=False,
                health_status=ServerHealthStatus.UNHEALTHY,
                created_at=now,
                updated_at=now,
            ),
        ],
        total=3,
        page=1,
        page_size=10,
        total_pages=1,
    )

    mock_tool_catalog.list_tools.side_effect = [
        PaginatedResponse[ToolResponse](
            items=[
                ToolResponse(
                    id=f"{server1_id}:calculate",
                    name="calculate",
                    description="Perform math",
                    input_schema={"type": "object", "properties": {"expr": {"type": "string"}}},
                    server_id=server1_id,
                    server_name="Math Server",
                    availability_status="AVAILABLE",
                    last_discovered_at=MagicMock(),
                )
            ],
            total=1,
            page=1,
            page_size=10,
            total_pages=1,
        ),
        PaginatedResponse[ToolResponse](
            items=[
                ToolResponse(
                    id=f"{server2_id}:calculate",
                    name="calculate",
                    description="Duplicate calculate",
                    input_schema={"type": "object"},
                    server_id=server2_id,
                    server_name="Text Server",
                    availability_status="AVAILABLE",
                    last_discovered_at=MagicMock(),
                ),
                ToolResponse(
                    id=f"{server2_id}:transform",
                    name="transform",
                    description="Transform text",
                    input_schema={"type": "object"},
                    server_id=server2_id,
                    server_name="Text Server",
                    availability_status="AVAILABLE",
                    last_discovered_at=MagicMock(),
                ),
            ],
            total=2,
            page=1,
            page_size=10,
            total_pages=1,
        ),
    ]

    tool_map = await gateway_service.refresh_tool_mappings()
    assert "math_server__calculate" in tool_map
    assert "text_server__calculate" in tool_map
    assert "text_server__transform" in tool_map
    assert len(tool_map) == 3


@pytest.mark.asyncio
async def test_refresh_tool_mappings_collision_handling(gateway_service, mock_registry, mock_tool_catalog):
    # Two distinct servers that both have the name "Postgres"
    srv1_id = uuid4()
    srv2_id = uuid4()
    now = datetime.now(UTC)

    mock_registry.list_servers.return_value = PaginatedResponse[ServerResponse](
        items=[
            ServerResponse(
                id=srv1_id,
                name="Postgres",
                transport=TransportType.STDIO,
                connection_config={"command": "python"},
                enabled=True,
                health_status=ServerHealthStatus.HEALTHY,
                created_at=now,
                updated_at=now,
            ),
            ServerResponse(
                id=srv2_id,
                name="Postgres",
                transport=TransportType.STDIO,
                connection_config={"command": "python"},
                enabled=True,
                health_status=ServerHealthStatus.HEALTHY,
                created_at=now,
                updated_at=now,
            ),
        ],
        total=2,
        page=1,
        page_size=10,
        total_pages=1,
    )

    mock_tool_catalog.list_tools.side_effect = [
        PaginatedResponse[ToolResponse](
            items=[
                ToolResponse(
                    id=f"{srv1_id}:query",
                    name="query",
                    description="Run query",
                    input_schema={},
                    server_id=srv1_id,
                    server_name="Postgres",
                    availability_status="AVAILABLE",
                    last_discovered_at=MagicMock(),
                )
            ],
            total=1,
            page=1,
            page_size=10,
            total_pages=1,
        ),
        PaginatedResponse[ToolResponse](
            items=[
                ToolResponse(
                    id=f"{srv2_id}:query",
                    name="query",
                    description="Run query",
                    input_schema={},
                    server_id=srv2_id,
                    server_name="Postgres",
                    availability_status="AVAILABLE",
                    last_discovered_at=MagicMock(),
                )
            ],
            total=1,
            page=1,
            page_size=10,
            total_pages=1,
        ),
    ]

    tool_map = await gateway_service.refresh_tool_mappings()
    assert "postgres__query" in tool_map
    short_id = str(srv2_id).replace("-", "")[:6]
    disambiguated = f"postgres_{short_id}__query"
    assert disambiguated in tool_map
    assert len(tool_map) == 2


@pytest.mark.asyncio
async def test_handle_call_tool_unknown(gateway_service):
    ctx = MagicMock()
    params = types.CallToolRequestParams(name="non_existent_tool", arguments={})
    res = await gateway_service.handle_call_tool(ctx, params)
    assert res.is_error is True
    assert "Unknown or unavailable tool" in res.content[0].text


@pytest.mark.asyncio
async def test_handle_call_tool_server_disabled(gateway_service, mock_registry):
    server_id = uuid4()
    gateway_service._tool_map["srv__tool"] = GatewayToolMapping(
        hub_tool_name="srv__tool",
        server_id=server_id,
        server_name="srv",
        original_tool_name="tool",
        input_schema={},
        description=None,
        availability_status="AVAILABLE",
    )

    mock_server = ServerEntity(
        id=server_id,
        name="srv",
        transport=TransportType.STDIO,
        enabled=False,
    )
    mock_registry.get_server_entity.return_value = mock_server

    ctx = MagicMock()
    params = types.CallToolRequestParams(name="srv__tool", arguments={})
    res = await gateway_service.handle_call_tool(ctx, params)
    assert res.is_error is True
    assert "disabled" in res.content[0].text


@pytest.mark.asyncio
async def test_handle_call_tool_validation_error(gateway_service, mock_registry, mock_tool_router):
    server_id = uuid4()
    gateway_service._tool_map["math__add"] = GatewayToolMapping(
        hub_tool_name="math__add",
        server_id=server_id,
        server_name="math",
        original_tool_name="add",
        input_schema={"type": "object", "properties": {"a": {"type": "number"}}, "required": ["a"]},
        description=None,
        availability_status="AVAILABLE",
    )

    mock_server = ServerEntity(
        id=server_id,
        name="math",
        transport=TransportType.STDIO,
        enabled=True,
    )
    mock_registry.get_server_entity.return_value = mock_server
    mock_tool_router.execute_mcp_tool.side_effect = ValidationError("Missing required property 'a'")

    ctx = MagicMock()
    params = types.CallToolRequestParams(name="math__add", arguments={})
    res = await gateway_service.handle_call_tool(ctx, params)
    assert res.is_error is True
    assert "Argument validation failed" in res.content[0].text


@pytest.mark.asyncio
async def test_handle_call_tool_success(gateway_service, mock_registry, mock_tool_router):
    server_id = uuid4()
    gateway_service._tool_map["math__calculate"] = GatewayToolMapping(
        hub_tool_name="math__calculate",
        server_id=server_id,
        server_name="math",
        original_tool_name="calculate",
        input_schema={},
        description=None,
        availability_status="AVAILABLE",
    )

    mock_server = ServerEntity(
        id=server_id,
        name="math",
        transport=TransportType.STDIO,
        enabled=True,
    )
    mock_registry.get_server_entity.return_value = mock_server
    mock_tool_router.execute_mcp_tool.return_value = types.CallToolResult(
        content=[types.TextContent(type="text", text="42")],
        is_error=False,
    )

    ctx = MagicMock()
    params = types.CallToolRequestParams(name="math__calculate", arguments={"expr": "6*7"})
    res = await gateway_service.handle_call_tool(ctx, params)
    assert res.is_error is False
    assert res.content[0].text == "42"
    mock_tool_router.execute_mcp_tool.assert_called_once_with(
        server_id=server_id,
        tool_name="calculate",
        arguments={"expr": "6*7"},
    )


@pytest.mark.asyncio
async def test_handle_list_tools_includes_meta_tools(gateway_service, mock_registry, mock_tool_catalog):
    mock_registry.list_servers.return_value = PaginatedResponse[ServerResponse](items=[], total=0, page=1, page_size=10, total_pages=0)
    mock_tool_catalog.list_tools.return_value = PaginatedResponse[ToolResponse](items=[], total=0, page=1, page_size=10, total_pages=0)

    ctx = MagicMock()
    result = await gateway_service.handle_list_tools(ctx)
    tool_names = [t.name for t in result.tools]

    assert SEARCH_TOOLS_NAME in tool_names
    assert MULTI_EXECUTE_TOOLS_NAME in tool_names


def test_get_tool_input_schema_meta_tools(gateway_service):
    assert gateway_service.get_tool_input_schema(SEARCH_TOOLS_NAME) == SEARCH_TOOLS_SCHEMA
    assert gateway_service.get_tool_input_schema(MULTI_EXECUTE_TOOLS_NAME) == MULTI_EXECUTE_TOOLS_SCHEMA
    assert gateway_service.get_tool_input_schema("non_existent") is None


@pytest.mark.asyncio
async def test_handle_call_tool_search_tools(gateway_service, mock_registry, mock_tool_catalog):
    server_id = uuid4()
    mock_registry.list_servers.return_value = PaginatedResponse[ServerResponse](items=[], total=0, page=1, page_size=10, total_pages=0)
    gateway_service._tool_map["math__calculate"] = GatewayToolMapping(
        hub_tool_name="math__calculate",
        server_id=server_id,
        server_name="math",
        original_tool_name="calculate",
        input_schema={"type": "object", "properties": {"expression": {"type": "string"}}},
        description="Math calculate",
        availability_status="AVAILABLE",
    )

    ctx = MagicMock()
    params = types.CallToolRequestParams(
        name=SEARCH_TOOLS_NAME,
        arguments={"queries": ["math calculate"]},
    )
    res = await gateway_service.handle_call_tool(ctx, params)
    assert res.is_error is False
    assert len(res.content) == 1
    data = json.loads(res.content[0].text)
    assert data["matched_count"] == 1
    assert data["tools"][0]["tool_slug"] == "math__calculate"


@pytest.mark.asyncio
async def test_handle_call_tool_multi_execute_tools(gateway_service, mock_registry, mock_tool_router):
    server_id = uuid4()
    mock_registry.list_servers.return_value = PaginatedResponse[ServerResponse](items=[], total=0, page=1, page_size=10, total_pages=0)
    gateway_service._tool_map["math__calculate"] = GatewayToolMapping(
        hub_tool_name="math__calculate",
        server_id=server_id,
        server_name="math",
        original_tool_name="calculate",
        input_schema={},
        description=None,
        availability_status="AVAILABLE",
    )

    mock_server = ServerEntity(
        id=server_id,
        name="math",
        transport=TransportType.STDIO,
        enabled=True,
    )
    mock_registry.get_server_entity.return_value = mock_server
    mock_tool_router.execute_mcp_tool.return_value = types.CallToolResult(
        content=[types.TextContent(type="text", text="42")],
        is_error=False,
    )

    ctx = MagicMock()
    params = types.CallToolRequestParams(
        name=MULTI_EXECUTE_TOOLS_NAME,
        arguments={
            "executions": [
                {"tool_slug": "math__calculate", "arguments": {"expr": "6*7"}},
                {"tool_slug": "invalid_slug", "arguments": {}},
            ]
        },
    )
    res = await gateway_service.handle_call_tool(ctx, params)
    assert res.is_error is False
    data = json.loads(res.content[0].text)
    assert len(data["results"]) == 2
    assert data["results"][0]["status"] == "success"
    assert data["results"][0]["data"] == "42"
    assert data["results"][1]["status"] == "error"
