"""Unit tests for ToolRouterService."""

from unittest.mock import AsyncMock
from uuid import uuid4

import mcp.types as mcp_types
import pytest

from app.core.enums.server_enum import ServerHealthStatus, TransportType
from app.core.exceptions import BadRequestError, ValidationError
from app.domain.server_entity import ServerEntity
from app.infrastructure.repositories.execution_repo import ExecutionRepositoryAbstract
from app.infrastructure.repositories.server_repo import ServerRepositoryAbstract
from app.schemas.connection import StdioConfig
from app.services.connection_manager import ConnectionManager
from app.services.server_registry import ServerRegistryService
from app.services.tool_catalog import ToolCatalogService
from app.services.tool_router import ToolRouterService


class MockConnectionManager(ConnectionManager):
    def __init__(self):
        super().__init__()

    async def list_tools(
        self, server: ServerEntity, timeout: float | None = None
    ) -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name="add",
                description="Add two numbers",
                input_schema={
                    "type": "object",
                    "properties": {
                        "a": {"type": "integer"},
                        "b": {"type": "integer"},
                    },
                    "required": ["a", "b"],
                },
            )
        ]

    async def call_tool(
        self,
        server: ServerEntity,
        tool_name: str,
        arguments: dict,
        timeout: float | None = None,
    ) -> mcp_types.CallToolResult:
        if tool_name == "add":
            res = arguments["a"] + arguments["b"]
            return mcp_types.CallToolResult(
                content=[mcp_types.TextContent(type="text", text=str(res))],
                structured_content={"result": res},
                is_error=False,
            )
        raise ValueError(f"Unknown tool: {tool_name}")


@pytest.fixture
def mock_server_repo() -> AsyncMock:
    repo = AsyncMock(spec=ServerRepositoryAbstract)
    repo.update.side_effect = lambda s: s
    return repo


@pytest.fixture
def mock_exec_repo() -> AsyncMock:
    repo = AsyncMock(spec=ExecutionRepositoryAbstract)
    repo.create.side_effect = lambda e: e
    return repo


@pytest.fixture
def tool_router_fixture(mock_server_repo: AsyncMock, mock_exec_repo: AsyncMock):
    server_reg = ServerRegistryService(mock_server_repo)
    conn_mgr = MockConnectionManager()
    catalog = ToolCatalogService()

    server = ServerEntity(
        id=uuid4(),
        name="math-server",
        transport=TransportType.STDIO,
        stdio_config=StdioConfig(command="python3"),
        enabled=True,
        health_status=ServerHealthStatus.HEALTHY,
    )
    mock_server_repo.get_by_id.return_value = server

    router = ToolRouterService(
        server_registry=server_reg,
        connection_manager=conn_mgr,
        tool_catalog=catalog,
        execution_repository=mock_exec_repo,
    )

    return router, server, mock_exec_repo, catalog, conn_mgr


async def test_execute_tool_success(tool_router_fixture):
    router, server, mock_exec_repo, catalog, conn_mgr = tool_router_fixture
    await catalog.refresh_server_tools(server, conn_mgr)

    resp = await router.execute_tool(
        server_id=server.id,
        tool_name="add",
        arguments={"a": 10, "b": 25},
    )

    assert resp.is_error is False
    assert resp.structured_content == {"result": 35}
    assert resp.duration_ms >= 0

    # Verify execution audit record was created
    mock_exec_repo.create.assert_awaited_once()
    saved = mock_exec_repo.create.call_args[0][0]
    assert saved.tool_name == "add"
    assert saved.is_error is False
    assert saved.response == {
        "content": [{"type": "text", "text": "35"}],
        "structured_content": {"result": 35},
    }


async def test_execute_tool_argument_validation_failure(tool_router_fixture):
    router, server, mock_exec_repo, catalog, conn_mgr = tool_router_fixture
    await catalog.refresh_server_tools(server, conn_mgr)

    # Missing required argument 'b'
    with pytest.raises(ValidationError) as exc_info:
        await router.execute_tool(
            server_id=server.id,
            tool_name="add",
            arguments={"a": 10},
        )
    assert "Invalid arguments" in str(exc_info.value)
    mock_exec_repo.create.assert_not_called()


async def test_execute_tool_on_disabled_server(tool_router_fixture):
    router, server, mock_exec_repo, _, _ = tool_router_fixture
    server.enabled = False

    with pytest.raises(BadRequestError):
        await router.execute_tool(
            server_id=server.id,
            tool_name="add",
            arguments={"a": 1, "b": 2},
        )
    mock_exec_repo.create.assert_not_called()
