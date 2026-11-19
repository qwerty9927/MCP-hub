"""Connecting hosted MCP servers with OAuth (ADR-0008).

A sign-in runs as a background task that opens an MCP session through the SDK's OAuth client. When the
server answers 401 the SDK discovers the authorization server, registers the hub (or uses a pre-registered
client), and calls our redirect handler with the authorization URL, which `start` returns to the browser.
The SDK then waits in our callback handler until `/oauth/callback` delivers the code; it exchanges it, the
session initializes, and the task saves the server and its encrypted credentials and syncs its tools.

Pending sign-ins live in this process (`OAuthFlowRegistry`), like the live sessions in ConnectionManager.
"""

import asyncio
import secrets
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import UUID

from mcp.client.auth import OAuthFlowError
from mcp.shared.auth import AuthorizationCodeResult, OAuthClientInformationFull

from app.core.config import Settings
from app.core.constants.oauth_constants import OAUTH_COMPLETE_TIMEOUT_SECONDS, OAUTH_START_TIMEOUT_SECONDS
from app.core.enums.server_enum import ServerAuthType, ServerHealthStatus, TransportType
from app.core.exceptions import AppError, BadGatewayError, BadRequestError, ConflictError, GatewayTimeoutError, NotFoundError
from app.core.logging import logger
from app.domain.server_entity import ServerEntity
from app.helpers.errors import find_oauth_error, format_mcp_error
from app.helpers.security import validate_http_url_resolved
from app.infrastructure.oauth.client_provider import (
    DbTokenStorage,
    HubOAuthClientProvider,
    MemoryTokenStorage,
    build_client_metadata,
    preregistered_client,
)
from app.infrastructure.oauth.provider_catalog import OAuthProvider, OAuthProviderCatalog
from app.infrastructure.repositories.oauth_credential_repository import OAuthCredentialRepositoryAbstract
from app.schemas.connection_schema import HttpConfig
from app.schemas.oauth_schema import OAuthConnectResponse, OAuthProviderResponse
from app.schemas.server_schema import ServerCreateRequest, ServerUpdateRequest
from app.services.connection_manager import ConnectionManager
from app.services.server_registry import ServerRegistryService
from app.services.tool_catalog import ToolCatalogService


@dataclass
class OAuthFlowResult:
    """How a sign-in ended."""

    server_id: UUID | None = None
    error: str | None = None


@dataclass
class PendingFlow:
    """One sign-in in progress."""

    user_id: UUID
    provider: OAuthProvider
    server_name: str
    existing_server_id: UUID | None = None  # set when re-authorizing a server
    state: str | None = None
    authorization_url: asyncio.Future[str] = field(default_factory=lambda: asyncio.get_running_loop().create_future())
    callback: asyncio.Future[AuthorizationCodeResult] = field(default_factory=lambda: asyncio.get_running_loop().create_future())
    task: asyncio.Task[OAuthFlowResult] | None = None


class OAuthFlowRegistry:
    """Sign-ins waiting for their callback, by OAuth state. One per process."""

    def __init__(self) -> None:
        self._flows: dict[str, PendingFlow] = {}

    def add(self, state: str, flow: PendingFlow) -> None:
        self._flows[state] = flow

    def pop(self, state: str) -> PendingFlow | None:
        return self._flows.pop(state, None)

    def get(self, state: str) -> PendingFlow | None:
        return self._flows.get(state)

    def __len__(self) -> int:
        return len(self._flows)

    async def shutdown(self) -> None:
        flows = list(self._flows.values())
        self._flows.clear()
        for flow in flows:
            if flow.task and not flow.task.done():
                flow.task.cancel()
        await asyncio.gather(*(flow.task for flow in flows if flow.task), return_exceptions=True)


class OAuthService:
    """Lists catalog providers and runs OAuth sign-ins that end in a registered, connected server."""

    def __init__(
        self,
        settings: Settings,
        catalog: OAuthProviderCatalog,
        registry: OAuthFlowRegistry,
        server_registry: ServerRegistryService,
        credentials: OAuthCredentialRepositoryAbstract,
        connection_manager: ConnectionManager,
        tool_catalog: ToolCatalogService,
    ) -> None:
        self.settings = settings
        self.catalog = catalog
        self.registry = registry
        self.server_registry = server_registry
        self.credentials = credentials
        self.connection_manager = connection_manager
        self.tool_catalog = tool_catalog

    async def list_providers(self, *, user_id: UUID) -> list[OAuthProviderResponse]:
        servers = await self.server_registry.list_server_entities(user_id=user_id)
        connected: dict[str, int] = {}
        for server in servers:
            if server.oauth_provider_id:
                connected[server.oauth_provider_id] = connected.get(server.oauth_provider_id, 0) + 1
        return [
            OAuthProviderResponse(
                id=provider.id,
                name=provider.name,
                description=provider.description,
                category=provider.category,
                mcp_url=provider.mcp_url,
                docs_url=provider.docs_url,
                logo=provider.logo,
                available=self._is_available(provider),
                setup_hint=None if self._is_available(provider) else self._setup_hint(provider),
                connected_count=connected.get(provider.id, 0),
            )
            for provider in self.catalog.list()
        ]

    async def start(self, *, user_id: UUID, provider_id: str, name: str | None = None) -> OAuthConnectResponse:
        """Begin connecting `provider_id` as a new server; returns the URL to send the user to."""
        provider = self._available_provider(provider_id)
        server_name = name.strip() if name else await self._free_name(provider.id, user_id=user_id)
        if await self.server_registry.name_is_taken(server_name, user_id=user_id):
            raise ConflictError(f"A server with name '{server_name}' already exists", details={"name": server_name})
        flow = PendingFlow(user_id=user_id, provider=provider, server_name=server_name)
        return await self._begin(flow, client_info=preregistered_client(self.settings, provider))

    async def reconnect(self, *, user_id: UUID, server_id: UUID) -> OAuthConnectResponse:
        """Sign in again for an OAuth server whose tokens can no longer be refreshed."""
        server = await self.server_registry.get_server_entity(server_id, user_id=user_id)
        if server.auth_type != ServerAuthType.OAUTH or not server.oauth_provider_id:
            raise BadRequestError("This server does not use OAuth", details={"server_id": str(server_id)})
        provider = self._available_provider(server.oauth_provider_id)
        stored = await DbTokenStorage(server_id, user_id, self.credentials).get_client_info()
        flow = PendingFlow(user_id=user_id, provider=provider, server_name=server.name, existing_server_id=server_id)
        return await self._begin(flow, client_info=stored or preregistered_client(self.settings, provider))

    async def complete(self, *, state: str, code: str | None, iss: str | None = None, error: str | None = None) -> OAuthFlowResult:
        """Deliver the authorization server's answer to the waiting sign-in and wait for it to finish."""
        flow = self.registry.pop(state)
        if flow is None or flow.task is None:
            return OAuthFlowResult(error="This sign-in has expired or was already used. Start again.")
        if error or not code:
            flow.callback.set_exception(OAuthFlowError(error or "No authorization code received"))
        else:
            flow.callback.set_result(AuthorizationCodeResult(code=code, state=state, iss=iss))
        try:
            return await asyncio.wait_for(asyncio.shield(flow.task), timeout=OAUTH_COMPLETE_TIMEOUT_SECONDS)
        except TimeoutError:
            flow.task.cancel()
            return OAuthFlowResult(error="Connecting the server took too long after sign-in.")

    def complete_redirect_url(self, result: OAuthFlowResult) -> str:
        """Where the callback sends the browser: the console's /oauth/complete page, with the result."""
        if result.server_id is not None:
            query = {"status": "success", "server_id": str(result.server_id)}
        else:
            query = {"status": "error", "error": result.error or "Sign-in failed"}
        return f"{self.settings.FRONTEND_BASE_URL}/oauth/complete?{urlencode(query)}"

    # -- internals ---------------------------------------------------------

    async def _begin(self, flow: PendingFlow, client_info: OAuthClientInformationFull | None) -> OAuthConnectResponse:
        await validate_http_url_resolved(flow.provider.mcp_url)
        flow.task = asyncio.create_task(self._run(flow, client_info))
        done, _ = await asyncio.wait(
            {flow.authorization_url, flow.task}, timeout=OAUTH_START_TIMEOUT_SECONDS, return_when=asyncio.FIRST_COMPLETED
        )
        if flow.authorization_url in done:
            return OAuthConnectResponse(authorization_url=flow.authorization_url.result(), state=flow.state)
        if flow.task in done:
            result = flow.task.result()
            if result.server_id is not None:  # the server needed no sign-in
                return OAuthConnectResponse(server_id=result.server_id)
            raise BadGatewayError(
                f"Could not start signing in to {flow.provider.name}: {result.error}",
                details={"provider_id": flow.provider.id, "reason": result.error},
            )
        flow.task.cancel()
        raise GatewayTimeoutError(
            f"{flow.provider.name} did not answer in time",
            details={"provider_id": flow.provider.id, "timeout_seconds": OAUTH_START_TIMEOUT_SECONDS},
        )

    async def _run(self, flow: PendingFlow, client_info: OAuthClientInformationFull | None) -> OAuthFlowResult:
        storage = MemoryTokenStorage(client_info=client_info)

        async def redirect_handler(authorization_url: str) -> None:
            state = parse_qs(urlparse(authorization_url).query).get("state", [None])[0]
            if not state:
                raise OAuthFlowError("Authorization URL has no state")
            flow.state = state
            self.registry.add(state, flow)
            flow.authorization_url.set_result(authorization_url)

        async def callback_handler() -> AuthorizationCodeResult:
            return await asyncio.wait_for(flow.callback, timeout=self.settings.OAUTH_FLOW_TIMEOUT_SECONDS)

        auth = HubOAuthClientProvider(
            server_url=flow.provider.mcp_url,
            client_metadata=build_client_metadata(self.settings, flow.provider),
            storage=storage,
            redirect_handler=redirect_handler,
            callback_handler=callback_handler,
        )
        # Not saved until the sign-in succeeds; the session runs in a ConnectionManager SessionWorker (AGENT.md).
        sign_in_server = ServerEntity(
            name=flow.server_name,
            transport=TransportType.STREAMABLE_HTTP,
            http_config=HttpConfig(url=flow.provider.mcp_url),
            user_id=flow.user_id,
            auth_type=ServerAuthType.OAUTH,
            oauth_provider_id=flow.provider.id,
        )
        try:
            await self.connection_manager.authorize(
                sign_in_server,
                auth,
                timeout=self.settings.OAUTH_FLOW_TIMEOUT_SECONDS + self.settings.DEFAULT_CONNECTION_TIMEOUT,
            )
            return await self._finish(flow, storage)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            message = _sign_in_error_message(exc)
            logger.warning(f"OAuth sign-in to '{flow.provider.id}' failed: {message}")
            return OAuthFlowResult(error=message)
        finally:
            if flow.state:
                self.registry.pop(flow.state)

    async def _finish(self, flow: PendingFlow, storage: MemoryTokenStorage) -> OAuthFlowResult:
        """Save the server and its credentials, then connect it and sync its tools."""
        if flow.existing_server_id is not None:
            server_id = flow.existing_server_id
            await self.connection_manager.disconnect(server_id)
            await self._point_at_provider_url(server_id, flow)
        else:
            created = await self.server_registry.create_server(
                ServerCreateRequest(
                    name=flow.server_name,
                    description=f"{flow.provider.name}: {flow.provider.description}",
                    transport=TransportType.STREAMABLE_HTTP,
                    http_config=HttpConfig(url=flow.provider.mcp_url),
                ),
                user_id=flow.user_id,
                auth_type=ServerAuthType.OAUTH,
                oauth_provider_id=flow.provider.id,
            )
            server_id = created.id

        db_storage = DbTokenStorage(server_id, flow.user_id, self.credentials)
        if storage.client_info is not None:
            await db_storage.set_client_info(storage.client_info)
        if storage.tokens is not None:
            await db_storage.set_tokens_with_expiry(storage.tokens, storage.expires_at)

        server = await self.server_registry.get_server_entity(server_id, user_id=flow.user_id)
        try:
            tools = await self.tool_catalog.refresh_server_tools(server, self.connection_manager)
            await self.server_registry.update_health(server_id, ServerHealthStatus.HEALTHY, len(tools), user_id=flow.user_id)
        except Exception as exc:  # the server is saved; a failed first sync is shown as its health, not a failed sign-in
            logger.warning(f"First tool sync for OAuth server {server_id} failed: {exc}")
            await self.server_registry.update_health(server_id, ServerHealthStatus.UNHEALTHY, user_id=flow.user_id)
        return OAuthFlowResult(server_id=server_id)

    async def _point_at_provider_url(self, server_id: UUID, flow: PendingFlow) -> None:
        """The new tokens are issued for the provider's current URL (RFC 8707 resource), which may have changed in the
        catalog since the server was created: move the server to it so the hub presents them where they are valid."""
        server = await self.server_registry.get_server_entity(server_id, user_id=flow.user_id)
        current = server.http_config
        if current is not None and current.url == flow.provider.mcp_url:
            return
        await self.server_registry.update_server(
            server_id,
            ServerUpdateRequest(http_config=HttpConfig(url=flow.provider.mcp_url, headers=current.headers if current else {})),
            user_id=flow.user_id,
        )
        logger.info(f"OAuth server {server_id} moved to {flow.provider.mcp_url} on reconnect")

    def _available_provider(self, provider_id: str) -> OAuthProvider:
        provider = self.catalog.get(provider_id)
        if provider is None:
            raise NotFoundError(f"Unknown provider '{provider_id}'", details={"provider_id": provider_id})
        if not self._is_available(provider):
            raise BadRequestError(
                f"{provider.name} needs setup before it can be connected",
                details={"provider_id": provider_id, "setup_hint": self._setup_hint(provider)},
            )
        return provider

    def _is_available(self, provider: OAuthProvider) -> bool:
        return not provider.requires_client or preregistered_client(self.settings, provider) is not None

    @staticmethod
    def _setup_hint(provider: OAuthProvider) -> str:
        return f'Register an OAuth app with {provider.name} and add it to OAUTH_CLIENTS as "{provider.id}"'

    async def _free_name(self, base: str, *, user_id: UUID) -> str:
        """`base`, or `base-2`, `base-3`… if the account already has a server with that name."""
        if not await self.server_registry.name_is_taken(base, user_id=user_id):
            return base
        for suffix in range(2, 100):
            candidate = f"{base}-{suffix}"
            if not await self.server_registry.name_is_taken(candidate, user_id=user_id):
                return candidate
        return f"{base}-{secrets.token_hex(3)}"


def _sign_in_error_message(exc: BaseException) -> str:
    """What to tell the user about a failed sign-in: the provider's OAuth error when there is one, else the connect failure."""
    oauth_error = find_oauth_error(exc)
    if oauth_error is not None:
        return str(oauth_error)
    if isinstance(exc, AppError) and isinstance(exc.details, dict) and exc.details.get("reason"):
        return str(exc.details["reason"])
    return format_mcp_error(exc)
