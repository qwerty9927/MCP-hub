"""Dependency injection providers for FastAPI routes."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.background_service.session_sweeper import SessionSweeperService
from app.core.exceptions import UnauthorizedError
from app.domain.principal_entity import Principal
from app.infrastructure.repositories.api_key_repository import ApiKeyRepositoryAbstract, PostgresApiKeyRepository
from app.infrastructure.repositories.execution_repository import (
    ExecutionRepositoryAbstract,
    PostgresExecutionRepository,
)
from app.infrastructure.repositories.ownership_repository import OwnershipRepositoryAbstract, PostgresOwnershipRepository
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
from app.infrastructure.repositories.user_repository import PostgresUserRepository, UserRepositoryAbstract
from app.mcp.mcp_server import MCPServer
from app.services.auth_service import AuthService
from app.services.connection_manager import ConnectionManager
from app.services.server_registry import ServerRegistryService
from app.services.session_explorer import SessionExplorerService
from app.services.session_tracker import SessionTrackerService
from app.services.tool_catalog import ToolCatalogService
from app.services.tool_executor import ToolExecutor

# Singleton instances for PostgreSQL repositories and managers
_server_repo: ServerRepositoryAbstract = PostgresServerRepository()
_tool_repo: ToolRepositoryAbstract = PostgresToolRepository()
_execution_repo: ExecutionRepositoryAbstract = PostgresExecutionRepository()
_session_repo: SessionRepositoryAbstract = PostgresSessionRepository()
_user_repo: UserRepositoryAbstract = PostgresUserRepository()
_api_key_repo: ApiKeyRepositoryAbstract = PostgresApiKeyRepository()
_ownership_repo: OwnershipRepositoryAbstract = PostgresOwnershipRepository()
_connection_manager = ConnectionManager()
_mcp_server: MCPServer | None = None

_bearer_security = HTTPBearer(auto_error=False, description="Console login token from POST /auth/login")


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


def get_auth_service() -> AuthService:
    """Return the account and API key service."""
    return AuthService(user_repository=_user_repo, api_key_repository=_api_key_repo, ownership_repository=_ownership_repo)


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_security)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> Principal:
    """Resolve the console login token on a REST request to its account, or raise 401."""
    if credentials is None:
        raise UnauthorizedError("Authentication required")

    principal = auth.authenticate_console(credentials.credentials)

    if principal is None:
        raise UnauthorizedError("Invalid or expired token")

    return principal


def get_connection_manager() -> ConnectionManager:
    """Return connection manager instance."""
    return _connection_manager


def get_tool_catalog_service() -> ToolCatalogService:
    """Return tool catalog service instance."""
    return ToolCatalogService(tool_repository=_tool_repo)


def get_server_registry_service() -> ServerRegistryService:
    """Return server registry service."""
    return ServerRegistryService(repository=get_server_repository())


def get_tool_executor_service() -> ToolExecutor:
    """Return the Execution module."""
    return ToolExecutor(
        server_registry=get_server_registry_service(),
        connection_manager=get_connection_manager(),
        tool_catalog=get_tool_catalog_service(),
        execution_repository=get_execution_repository(),
        session_repository=get_session_repository(),
    )


def get_session_explorer_service() -> SessionExplorerService:
    """Return session explorer service."""
    return SessionExplorerService(
        session_repository=get_session_repository(),
        execution_repository=get_execution_repository(),
    )


def get_session_sweeper_service() -> SessionSweeperService:
    """Return the background job that completes idle Sessions."""
    return SessionSweeperService(session_repository=get_session_repository())


def get_session_tracker_service() -> SessionTrackerService:
    return SessionTrackerService(session_repository=get_session_repository())


def get_mcp_server() -> MCPServer:
    """Return singleton MCPServer instance."""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MCPServer(
            server_registry=get_server_registry_service(),
            tool_catalog=get_tool_catalog_service(),
            connection_manager=get_connection_manager(),
            tool_executor=get_tool_executor_service(),
            session_tracker=get_session_tracker_service(),
            auth_service=get_auth_service(),
        )

    return _mcp_server
