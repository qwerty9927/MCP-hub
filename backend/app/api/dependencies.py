"""Dependency injection providers for FastAPI routes."""

from app.infrastructure.repositories.execution_repo import (
    ExecutionRepositoryAbstract,
    SqliteExecutionRepository,
)
from app.infrastructure.repositories.server_repo import (
    ServerRepositoryAbstract,
    SqliteServerRepository,
)
from app.infrastructure.repositories.tool_repo import (
    SqliteToolRepository,
    ToolRepositoryAbstract,
)
from app.services.connection_manager import ConnectionManager
from app.services.mcp_gateway import MCPGatewayService
from app.services.server_registry import ServerRegistryService
from app.services.tool_catalog import ToolCatalogService
from app.services.tool_router import ToolRouterService

# Singleton instances for SQLite repositories and managers
_server_repo: ServerRepositoryAbstract = SqliteServerRepository()
_tool_repo: ToolRepositoryAbstract = SqliteToolRepository()
_execution_repo: ExecutionRepositoryAbstract = SqliteExecutionRepository()
_connection_manager = ConnectionManager()
_tool_catalog = ToolCatalogService(repository=_tool_repo)
_mcp_gateway: MCPGatewayService | None = None


def get_server_repository() -> ServerRepositoryAbstract:
    """Return server repository instance."""
    return _server_repo


def get_tool_repository() -> ToolRepositoryAbstract:
    """Return tool repository instance."""
    return _tool_repo


def get_execution_repository() -> ExecutionRepositoryAbstract:
    """Return execution repository instance."""
    return _execution_repo


def get_connection_manager() -> ConnectionManager:
    """Return connection manager instance."""
    return _connection_manager


def get_tool_catalog() -> ToolCatalogService:
    """Return tool catalog service instance."""
    return _tool_catalog


def get_server_registry_service() -> ServerRegistryService:
    """Return server registry service."""
    return ServerRegistryService(repository=get_server_repository())


def get_tool_router_service() -> ToolRouterService:
    """Return tool router service."""
    return ToolRouterService(
        server_registry=get_server_registry_service(),
        connection_manager=get_connection_manager(),
        tool_catalog=get_tool_catalog(),
        execution_repository=get_execution_repository(),
    )


def get_mcp_gateway() -> MCPGatewayService:
    """Return singleton MCPGatewayService instance."""
    global _mcp_gateway
    if _mcp_gateway is None:
        _mcp_gateway = MCPGatewayService(
            server_registry=get_server_registry_service(),
            tool_catalog=get_tool_catalog(),
            connection_manager=get_connection_manager(),
            tool_router=get_tool_router_service(),
        )
    return _mcp_gateway
