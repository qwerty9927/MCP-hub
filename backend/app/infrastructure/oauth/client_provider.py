"""Glue between the hub and the MCP SDK's OAuth client (`mcp.client.auth.OAuthClientProvider`), ADR-0008.

The SDK does discovery, dynamic client registration, PKCE, token exchange and refresh. The hub supplies
where credentials live (a DB-backed or in-memory `TokenStorage`) and, during a sign-in only, the handlers
that hand the authorization URL to the browser and wait for the callback.
"""

import time
from uuid import UUID

from mcp.client.auth import OAuthClientProvider, OAuthFlowError
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

from app.core.config import Settings
from app.infrastructure.oauth.provider_catalog import OAuthProvider
from app.infrastructure.repositories.oauth_credential_repository import OAuthCredentialRepositoryAbstract

CLIENT_NAME = "MCP Hub"


def callback_url(settings: Settings) -> str:
    """The redirect URI registered with every authorization server."""
    return f"{settings.PUBLIC_API_BASE_URL}{settings.API_V1_STR}/oauth/callback"


def build_client_metadata(settings: Settings, provider: OAuthProvider | None) -> OAuthClientMetadata:
    """Metadata the hub registers itself with: a public web client using the authorization-code grant."""
    return OAuthClientMetadata(
        client_name=CLIENT_NAME,
        redirect_uris=[callback_url(settings)],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="none",
        scope=provider.scopes if provider else None,
        application_type="web",
    )


def preregistered_client(settings: Settings, provider: OAuthProvider) -> OAuthClientInformationFull | None:
    """The admin-configured client for a provider without dynamic client registration, if any."""
    config = settings.OAUTH_CLIENTS.get(provider.id)
    if not config or not config.get("client_id"):
        return None
    secret = config.get("client_secret")
    return OAuthClientInformationFull(
        client_id=config["client_id"],
        client_secret=secret,
        redirect_uris=[callback_url(settings)],
        token_endpoint_auth_method="client_secret_post" if secret else "none",
    )


def _expires_at(tokens: OAuthToken) -> float | None:
    return time.time() + int(tokens.expires_in) if tokens.expires_in is not None else None


def _with_remaining_lifetime(tokens: OAuthToken, expires_at: float | None) -> OAuthToken:
    """Stored tokens carry an absolute expiry; the SDK reads a relative `expires_in`."""
    if expires_at is None:
        return tokens
    return tokens.model_copy(update={"expires_in": max(0, int(expires_at - time.time()))})


class MemoryTokenStorage:
    """Credentials held only for the duration of one sign-in, persisted once it succeeds."""

    def __init__(self, client_info: OAuthClientInformationFull | None = None) -> None:
        self.client_info = client_info
        self.tokens: OAuthToken | None = None
        self.expires_at: float | None = None

    async def get_tokens(self) -> OAuthToken | None:
        return _with_remaining_lifetime(self.tokens, self.expires_at) if self.tokens else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self.tokens = tokens
        self.expires_at = _expires_at(tokens)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self.client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self.client_info = client_info


class DbTokenStorage:
    """A server's stored credentials; refreshed tokens are written back as the SDK obtains them."""

    def __init__(self, server_id: UUID, repository: OAuthCredentialRepositoryAbstract) -> None:
        self.server_id = server_id
        self.repository = repository

    async def get_tokens(self) -> OAuthToken | None:
        record = await self.repository.get(self.server_id)
        if record is None or record.tokens_json is None:
            return None
        return _with_remaining_lifetime(OAuthToken.model_validate_json(record.tokens_json), record.access_token_expires_at)

    async def set_tokens(self, tokens: OAuthToken) -> None:
        await self.repository.save_tokens(self.server_id, tokens.model_dump_json(), _expires_at(tokens))

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        record = await self.repository.get(self.server_id)
        if record is None or record.client_info_json is None:
            return None
        return OAuthClientInformationFull.model_validate_json(record.client_info_json)

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        await self.repository.save_client_info(self.server_id, client_info.model_dump_json())


class HubOAuthClientProvider(OAuthClientProvider):
    """The SDK provider, plus: tokens loaded from storage keep their expiry, so an expired one is refreshed
    up front instead of being sent, rejected with 401 and sent down the full sign-in path."""

    async def _initialize(self) -> None:
        await super()._initialize()
        tokens = self.context.current_tokens
        if tokens is not None and tokens.expires_in is not None:
            self.context.update_token_expiry(tokens)


def find_oauth_error(exc: BaseException | None) -> OAuthFlowError | None:
    """The OAuthFlowError inside `exc` (directly, in an exception group, or in its cause/context chain)."""
    seen: set[int] = set()
    stack: list[BaseException] = [exc] if exc is not None else []
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, OAuthFlowError):
            return current
        if isinstance(current, BaseExceptionGroup):
            stack.extend(current.exceptions)
        for linked in (current.__cause__, current.__context__):
            if linked is not None:
                stack.append(linked)
    return None
