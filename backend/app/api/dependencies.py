"""Dependency injection providers for FastAPI routes."""

from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.background_service.embedding_backfill import EmbeddingBackfillService
from app.background_service.session_sweeper import SessionSweeperService
from app.core.config import get_settings
from app.core.constants.auth_constants import CONSOLE_CLIENT_HEADER, CONSOLE_CLIENT_HEADER_VALUE
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.domain.principal_entity import Principal
from app.helpers.crypto import SecretCipher
from app.infrastructure.embedding.embedding_factory import create_embedding_service
from app.infrastructure.embedding.embedding_service import EmbeddingServiceAbstract
from app.infrastructure.oauth.provider_catalog import get_provider_catalog
from app.infrastructure.repositories.api_key_repository import ApiKeyRepositoryAbstract, PostgresApiKeyRepository
from app.infrastructure.repositories.auth_rate_limit_repository import PostgresAuthRateLimitRepository
from app.infrastructure.repositories.execution_repository import (
    ExecutionRepositoryAbstract,
    PostgresExecutionRepository,
)
from app.infrastructure.repositories.oauth_credential_repository import (
    OAuthCredentialRepositoryAbstract,
    PostgresOAuthCredentialRepository,
)
from app.infrastructure.repositories.refresh_token_repository import PostgresRefreshTokenRepository, RefreshTokenRepositoryAbstract
from app.infrastructure.repositories.server_repository import (
    PostgresServerRepository,
    ServerRepositoryAbstract,
)
from app.infrastructure.repositories.session_repository import (
    PostgresSessionRepository,
    SessionRepositoryAbstract,
)
from app.infrastructure.repositories.tool_access_repository import PostgresToolAccessRepository, ToolAccessRepositoryAbstract
from app.infrastructure.repositories.tool_repository import (
    PostgresToolRepository,
    ToolRepositoryAbstract,
)
from app.infrastructure.repositories.user_repository import PostgresUserRepository, UserRepositoryAbstract
from app.mcp.mcp_server import MCPServer
from app.services.auth_rate_limiter import AuthRateLimiter
from app.services.auth_service import AuthService
from app.services.connection_manager import ConnectionManager
from app.services.oauth_service import OAuthFlowRegistry, OAuthService
from app.services.server_registry import ServerRegistryService
from app.services.session_explorer import SessionExplorerService
from app.services.session_tracker import SessionTrackerService
from app.services.tool_access_service import ToolAccessService
from app.services.tool_catalog import ToolCatalogService
from app.services.tool_executor import ToolExecutor

# Singleton instances for PostgreSQL repositories and managers
_server_repository: ServerRepositoryAbstract = PostgresServerRepository()
_tool_repository: ToolRepositoryAbstract = PostgresToolRepository()
_execution_repository: ExecutionRepositoryAbstract = PostgresExecutionRepository()
_session_repository: SessionRepositoryAbstract = PostgresSessionRepository()
_user_repository: UserRepositoryAbstract = PostgresUserRepository()
_api_key_repository: ApiKeyRepositoryAbstract = PostgresApiKeyRepository()
_refresh_token_repository: RefreshTokenRepositoryAbstract = PostgresRefreshTokenRepository()
_tool_access_repository: ToolAccessRepositoryAbstract = PostgresToolAccessRepository()
_settings = get_settings()
_oauth_credential_repository: OAuthCredentialRepositoryAbstract = PostgresOAuthCredentialRepository(
    SecretCipher(_settings.OAUTH_ENCRYPTION_KEY)
)
_oauth_flow_registry = OAuthFlowRegistry()
_auth_rate_limiter = AuthRateLimiter(PostgresAuthRateLimitRepository(), get_settings)
_connection_manager = ConnectionManager(oauth_credentials=_oauth_credential_repository)
# Local fastembed or Cloudflare Workers AI, picked once from EMBEDDING_PROVIDER (ADR-0010).
_embedding_service: EmbeddingServiceAbstract = create_embedding_service(_settings)
_mcp_server: MCPServer | None = None

_bearer_security = HTTPBearer(auto_error=False, description="Console login token from POST /auth/login")


def get_server_repository() -> ServerRepositoryAbstract:
    """Return server repository instance."""
    return _server_repository


def get_tool_access_repository() -> ToolAccessRepositoryAbstract:
    """Return the per-API-key tool visibility repository (ADR-0007)."""
    return _tool_access_repository


def get_tool_repository() -> ToolRepositoryAbstract:
    """Return tool repository instance."""
    return _tool_repository


def get_execution_repository() -> ExecutionRepositoryAbstract:
    """Return execution repository instance."""
    return _execution_repository


def get_session_repository() -> SessionRepositoryAbstract:
    """Return session repository instance."""
    return _session_repository


def get_auth_service() -> AuthService:
    """Return the account, console sign-in and API key service."""
    return AuthService(
        user_repository=_user_repository,
        api_key_repository=_api_key_repository,
        refresh_token_repository=_refresh_token_repository,
    )


def get_auth_rate_limiter() -> AuthRateLimiter:
    """Return the rate limiter for the unauthenticated /auth endpoints."""
    return _auth_rate_limiter


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Principal:
    """Resolve the console login token on a REST request to its account, or raise 401."""
    if credentials is None:
        raise UnauthorizedError("Authentication required")

    principal = await auth_service.authenticate_console_user(credentials.credentials)

    if principal is None:
        raise UnauthorizedError("Invalid or expired token")

    return principal


def require_console_client(
    console_client: Annotated[str | None, Header(alias=CONSOLE_CLIENT_HEADER, include_in_schema=False)] = None,
) -> None:
    """CSRF check for the endpoints that act on the refresh token cookie (ADR-0009).

    A cross-site page cannot add a custom header without a CORS preflight, which only CORS_ORIGINS pass.
    """
    if console_client != CONSOLE_CLIENT_HEADER_VALUE:
        raise ForbiddenError(f"Missing {CONSOLE_CLIENT_HEADER} header")


def get_oauth_flow_registry() -> OAuthFlowRegistry:
    """Return the process-wide registry of OAuth sign-ins in progress (ADR-0008)."""
    return _oauth_flow_registry


def get_oauth_service() -> OAuthService:
    """Return the service that connects hosted MCP servers with OAuth (ADR-0008)."""
    return OAuthService(
        settings=_settings,
        catalog=get_provider_catalog(),
        registry=_oauth_flow_registry,
        server_registry=get_server_registry_service(),
        credentials=_oauth_credential_repository,
        connection_manager=_connection_manager,
        tool_catalog=get_tool_catalog_service(),
    )


def get_connection_manager() -> ConnectionManager:
    """Return connection manager instance."""
    return _connection_manager


def get_embedding_service() -> EmbeddingServiceAbstract:
    """Return the embedding model used for tool search (loaded on first use)."""
    return _embedding_service


def get_tool_access_service() -> ToolAccessService:
    """Return the per-API-key tool visibility service (ADR-0007)."""
    return ToolAccessService(
        api_key_repository=_api_key_repository,
        server_registry=get_server_registry_service(),
        tool_repository=get_tool_repository(),
        tool_access_repository=get_tool_access_repository(),
    )


def get_tool_catalog_service() -> ToolCatalogService:
    """Return tool catalog service instance."""
    return ToolCatalogService(tool_repository=_tool_repository, embedding_service=get_embedding_service())


def get_server_registry_service() -> ServerRegistryService:
    """Return server registry service."""
    return ServerRegistryService(server_repository=get_server_repository())


def get_tool_executor_service() -> ToolExecutor:
    """Return the Execution module."""
    return ToolExecutor(
        server_registry=get_server_registry_service(),
        connection_manager=get_connection_manager(),
        tool_catalog=get_tool_catalog_service(),
        execution_repository=get_execution_repository(),
        session_repository=get_session_repository(),
        tool_access_repository=get_tool_access_repository(),
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


def get_embedding_backfill_service() -> EmbeddingBackfillService:
    """Return the background job that embeds Tools stored without an embedding."""
    return EmbeddingBackfillService(
        tool_repository=get_tool_repository(),
        embedding_service=get_embedding_service(),
        batch_size=_settings.EMBEDDING_BACKFILL_BATCH,
        queued=_settings.EMBEDDING_BACKFILL_QUEUED,
    )


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
