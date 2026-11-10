"""Dependency injection providers for FastAPI routes."""

from app.infrastructure.repositories.execution_repository import (
    ExecutionRepositoryAbstract,
    PostgresExecutionRepository,
)
from app.infrastructure.repositories.server_repository import (
    PostgresServerRepository,
    ServerRepositoryAbstract,
)
from app.infrastructure.repositories.session_repository import (
    PostgresSessionRepository,
    SessionRepositoryAbstract,
)
from app.infrastructure.repositories.tool_repository import (
    PostgresToolRepository,
    ToolRepositoryAbstract,
)
from app.mcp.mcp_server import MCPServer
from app.services.connection_manager import ConnectionManager
from app.services.server_registry import ServerRegistryService
from app.services.session_explorer import SessionExplorerService
from app.services.tool_catalog import ToolCatalogService
from app.services.tool_executor import ToolExecutor

# Singleton instances for PostgreSQL repositories and managers
_server_repo: ServerRepositoryAbstract = PostgresServerRepository()
_tool_repo: ToolRepositoryAbstract = PostgresToolRepository()
_execution_repo: ExecutionRepositoryAbstract = PostgresExecutionRepository()
_session_repo: SessionRepositoryAbstract = PostgresSessionRepository()
_connection_manager = ConnectionManager()
_tool_catalog = ToolCatalogService(repository=_tool_repo)
_mcp_server: MCPServer | None = None


def get_server_repository() -> ServerRepositoryAbstract:
    """Return server repository instance."""
    return _server_repo


def get_tool_repository() -> ToolRepositoryAbstract:
    """Return tool repository instance."""
    return _tool_repo


def get_execution_repository() -> ExecutionRepositoryAbstract:
    """Return execution repository instance."""
    return _execution_repo


def get_session_repository() -> SessionRepositoryAbstract:
    """Return session repository instance."""
    return _session_repo


def get_connection_manager() -> ConnectionManager:
    """Return connection manager instance."""
    return _connection_manager


def get_tool_catalog() -> ToolCatalogService:
    """Return tool catalog service instance."""
    return _tool_catalog


def get_server_registry_service() -> ServerRegistryService:
    """Return server registry service."""
    return ServerRegistryService(repository=get_server_repository())


def get_tool_executor() -> ToolExecutor:
    """Return the Execution module."""
    return ToolExecutor(
        server_registry=get_server_registry_service(),
        connection_manager=get_connection_manager(),
        tool_catalog=get_tool_catalog(),
        execution_repository=get_execution_repository(),
        session_repository=get_session_repository(),
    )


def get_session_explorer_service() -> SessionExplorerService:
    """Return session explorer service."""
    return SessionExplorerService(
        session_repository=get_session_repository(),
        execution_repository=get_execution_repository(),
    )


def get_mcp_server() -> MCPServer:
    """Return singleton MCPServer instance."""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MCPServer(
            server_registry=get_server_registry_service(),
            tool_catalog=get_tool_catalog(),
            connection_manager=get_connection_manager(),
            tool_executor=get_tool_executor(),
            session_repository=get_session_repository(),
        )
    return _mcp_server


# Backward-compatible alias
get_mcp_gateway = get_mcp_server
