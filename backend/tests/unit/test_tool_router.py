"""Unit tests for ToolRouterService."""

from uuid import uuid4

import mcp.types as mcp_types
import pytest

from app.core.exceptions import BadRequestError, ValidationError
from app.domain.server_entity import ServerEntity
from app.infrastructure.repositories.execution_repo import InMemoryExecutionRepository
from app.infrastructure.repositories.server_repo import InMemoryServerRepository
from app.schemas.server import ServerHealthStatus, StdioConfig, TransportType
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
async def tool_router_fixture():
    server_repo = InMemoryServerRepository()
    exec_repo = InMemoryExecutionRepository()
    server_reg = ServerRegistryService(server_repo)
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
    await server_repo.create(server)
    await catalog.refresh_server_tools(server, conn_mgr)

    router = ToolRouterService(
        server_registry=server_reg,
        connection_manager=conn_mgr,
        tool_catalog=catalog,
        execution_repository=exec_repo,
    )

    return router, server, exec_repo


async def test_execute_tool_success(tool_router_fixture):
    router, server, exec_repo = tool_router_fixture

    resp = await router.execute_tool(
        server_id=server.id,
        tool_name="add",
        arguments={"a": 10, "b": 25},
    )

    assert resp.is_error is False
    assert resp.structured_content == {"result": 35}
    assert resp.duration_ms >= 0

    # Verify execution audit record was created
    executions, total = await exec_repo.list()
    assert total == 1
    assert executions[0].tool_name == "add"
    assert executions[0].is_error is False


async def test_execute_tool_argument_validation_failure(tool_router_fixture):
    router, server, _ = tool_router_fixture

    # Missing required argument 'b'
    with pytest.raises(ValidationError) as exc_info:
        await router.execute_tool(
            server_id=server.id,
            tool_name="add",
            arguments={"a": 10},
        )
    assert "Invalid arguments" in str(exc_info.value)


async def test_execute_tool_on_disabled_server(tool_router_fixture):
    router, server, _ = tool_router_fixture
    server.enabled = False

    with pytest.raises(BadRequestError):
        await router.execute_tool(
            server_id=server.id,
            tool_name="add",
            arguments={"a": 1, "b": 2},
        )
