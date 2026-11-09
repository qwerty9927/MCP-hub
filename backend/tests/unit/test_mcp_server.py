"""Unit tests for MCPServer."""

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
from app.domain.server_entity import ServerEntity
from app.domain.tool_entity import ToolEntity
from app.helpers.text import slugify
from app.mcp.mcp_server import MCPServer
from app.mcp.multi_execute_tools import MULTI_EXECUTE_TOOLS_SCHEMA
from app.mcp.search_tools import SEARCH_TOOLS_SCHEMA
from app.schemas.common import PaginatedResponse
from app.schemas.server import ServerResponse
from app.schemas.tool import ToolResponse


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
def mock_session_explorer():
    return AsyncMock()


@pytest.fixture
def mcp_server_instance(mock_registry, mock_tool_catalog, mock_connection_mgr, mock_tool_router, mock_session_explorer):
    return MCPServer(
        server_registry=mock_registry,
        tool_catalog=mock_tool_catalog,
        connection_manager=mock_connection_mgr,
        tool_router=mock_tool_router,
        session_explorer=mock_session_explorer,
    )


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.session = MagicMock()
    ctx.session._connection = MagicMock()
    ctx.session._connection.session_id = "test-session-123"
    ctx.session._connection.client_params = None
    return ctx


def test_slugify_name():
    assert slugify("Github Tools") == "github_tools"
    assert slugify("Postgres-DB #1") == "postgres_db_1"
    assert slugify("  --- special ---  ") == "special"
    assert slugify("!!!") == "server"


@pytest.mark.asyncio
async def test_handle_list_tools_strictly_two_tools(mcp_server_instance, mock_context):
    result = await mcp_server_instance.handle_list_tools(mock_context)
    tool_names = [t.name for t in result.tools]

    assert len(result.tools) == 2
    assert SEARCH_TOOLS_NAME in tool_names
    assert MULTI_EXECUTE_TOOLS_NAME in tool_names


def test_get_tool_input_schema_meta_tools(mcp_server_instance):
    assert mcp_server_instance.get_tool_input_schema(SEARCH_TOOLS_NAME) == SEARCH_TOOLS_SCHEMA
    assert mcp_server_instance.get_tool_input_schema(MULTI_EXECUTE_TOOLS_NAME) == MULTI_EXECUTE_TOOLS_SCHEMA
    assert mcp_server_instance.get_tool_input_schema("non_existent") is None


@pytest.mark.asyncio
async def test_handle_call_tool_requires_session_id(mcp_server_instance):
    ctx_no_session = MagicMock()
    ctx_no_session.session = None

    params = types.CallToolRequestParams(name=SEARCH_TOOLS_NAME, arguments={"queries": ["test"]})
    res = await mcp_server_instance.handle_call_tool(ctx_no_session, params)

    assert res.is_error is True
    assert "Header mcp-session-id is required" in res.content[0].text


@pytest.mark.asyncio
async def test_handle_call_tool_rejects_unadvertised_direct_tool(mcp_server_instance, mock_context):
    params = types.CallToolRequestParams(name="math_server__calculate", arguments={})
    res = await mcp_server_instance.handle_call_tool(mock_context, params)

    assert res.is_error is True
    assert "Unknown tool" in res.content[0].text
    assert SEARCH_TOOLS_NAME in res.content[0].text
    assert MULTI_EXECUTE_TOOLS_NAME in res.content[0].text


@pytest.mark.asyncio
async def test_handle_call_tool_search_tools(mcp_server_instance, mock_registry, mock_tool_catalog, mock_context):
    server_id = uuid4()
    now = datetime.now(UTC)

    mock_registry.list_servers.return_value = PaginatedResponse[ServerResponse](
        items=[
            ServerResponse(
                id=server_id,
                name="math",
                transport=TransportType.STDIO,
                connection_config={"command": "python"},
                enabled=True,
                health_status=ServerHealthStatus.HEALTHY,
                created_at=now,
                updated_at=now,
            )
        ],
        total=1,
        page=1,
        page_size=10,
        total_pages=1,
    )

    mock_tool_catalog.list_tools.return_value = PaginatedResponse[ToolResponse](
        items=[
            ToolResponse(
                id=f"{server_id}:calculate",
                name="calculate",
                description="Math calculate",
                input_schema={"type": "object", "properties": {"expression": {"type": "string"}}},
                server_id=server_id,
                server_name="math",
                availability_status="AVAILABLE",
                last_discovered_at=MagicMock(),
            )
        ],
        total=1,
        page=1,
        page_size=10,
        total_pages=1,
    )

    params = types.CallToolRequestParams(
        name=SEARCH_TOOLS_NAME,
        arguments={"queries": ["math calculate"]},
    )
    res = await mcp_server_instance.handle_call_tool(mock_context, params)
    assert res.is_error is False
    assert len(res.content) == 1
    data = json.loads(res.content[0].text)
    assert data["matched_count"] == 1
    assert data["tools"][0]["tool_slug"] == "math__calculate"


@pytest.mark.asyncio
async def test_handle_call_tool_multi_execute_tools(mcp_server_instance, mock_registry, mock_tool_catalog, mock_tool_router, mock_context):
    server_id = uuid4()
    now = datetime.now(UTC)

    mock_registry.list_servers.return_value = PaginatedResponse[ServerResponse](
        items=[
            ServerResponse(
                id=server_id,
                name="math",
                transport=TransportType.STDIO,
                connection_config={"command": "python"},
                enabled=True,
                health_status=ServerHealthStatus.HEALTHY,
                created_at=now,
                updated_at=now,
            )
        ],
        total=1,
        page=1,
        page_size=10,
        total_pages=1,
    )

    mock_server = ServerEntity(
        id=server_id,
        name="math",
        transport=TransportType.STDIO,
        enabled=True,
    )
    mock_registry.get_server_entity.return_value = mock_server

    mock_tool = ToolEntity(
        id=f"{server_id}:calculate",
        server_id=server_id,
        server_name="math",
        name="calculate",
        description=None,
        input_schema={},
        availability_status="AVAILABLE",
        last_discovered_at=now,
    )
    mock_tool_catalog.get_tool.return_value = mock_tool

    mock_tool_router.execute_mcp_tool.return_value = types.CallToolResult(
        content=[types.TextContent(type="text", text="42")],
        is_error=False,
    )

    params = types.CallToolRequestParams(
        name=MULTI_EXECUTE_TOOLS_NAME,
        arguments={
            "executions": [
                {"tool_slug": "math__calculate", "arguments": {"expr": "6*7"}},
                {"tool_slug": "invalid_slug", "arguments": {}},
            ]
        },
    )
    res = await mcp_server_instance.handle_call_tool(mock_context, params)
    assert res.is_error is False
    data = json.loads(res.content[0].text)
    assert len(data["results"]) == 2
    assert data["results"][0]["status"] == "success"
    assert data["results"][0]["data"] == "42"
    assert data["results"][1]["status"] == "error"
