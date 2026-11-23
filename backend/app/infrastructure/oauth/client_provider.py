"""Glue between the hub and the MCP SDK's OAuth client (`mcp.client.auth.OAuthClientProvider`), ADR-0008.

The SDK does discovery, dynamic client registration, PKCE, token exchange and refresh. The hub supplies
where credentials live (a DB-backed or in-memory `TokenStorage`) and, during a sign-in only, the handlers
that hand the authorization URL to the browser and wait for the callback.

The SDK keeps what it discovers about the authorization server in memory only. The hub stores it with the
credentials (`OAuthDiscovery`) and restores it for every later session, so a refresh goes to the real token
endpoint and not to the SDK's `<server origin>/token` guess.
"""

import time
from uuid import UUID

import httpx2
from mcp.client.auth import OAuthClientProvider
from mcp.client.auth.oauth2 import OAuthContext
from mcp.client.auth.utils import (
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
    create_oauth_metadata_request,
    handle_auth_metadata_response,
    handle_protected_resource_response,
    validate_metadata_issuer,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthMetadata, OAuthToken, ProtectedResourceMetadata
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.constants.oauth_constants import OAUTH_CLIENT_NAME, OAUTH_DISCOVERY_TIMEOUT_SECONDS
from app.core.logging import logger
from app.infrastructure.oauth.provider_catalog import OAuthProvider
from app.infrastructure.repositories.oauth_credential_repository import OAuthCredentialRepositoryAbstract


class OAuthDiscovery(BaseModel):
    """Where a server's authorization server is and how to reach it (its token endpoint above all)."""

    auth_server_url: str | None = None
    protected_resource_metadata: ProtectedResourceMetadata | None = None
    oauth_metadata: OAuthMetadata | None = None

    @classmethod
    def from_context(cls, context: OAuthContext) -> "OAuthDiscovery | None":
        """What the SDK discovered during a sign-in, or None if it discovered nothing."""
        if context.oauth_metadata is None:
            return None
        return cls(
            auth_server_url=context.auth_server_url,
            protected_resource_metadata=context.protected_resource_metadata,
            oauth_metadata=context.oauth_metadata,
        )

    def apply_to(self, context: OAuthContext) -> None:
        context.auth_server_url = self.auth_server_url
        context.protected_resource_metadata = self.protected_resource_metadata
        context.oauth_metadata = self.oauth_metadata


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

    def __init__(self, server_id: UUID, user_id: UUID, repository: OAuthCredentialRepositoryAbstract) -> None:
        self.server_id = server_id
        self.user_id = user_id
        self.repository = repository

    async def get_tokens(self) -> OAuthToken | None:
        record = await self.repository.get(self.server_id, user_id=self.user_id)
        if record is None or record.tokens_json is None:
            return None
        return _with_remaining_lifetime(OAuthToken.model_validate_json(record.tokens_json), record.access_token_expires_at)

    async def set_tokens(self, tokens: OAuthToken) -> None:
        await self.repository.save_tokens(self.server_id, tokens.model_dump_json(), _expires_at(tokens), user_id=self.user_id)

    async def set_tokens_with_expiry(self, tokens: OAuthToken, expires_at: float | None) -> None:
        """Store tokens obtained earlier, keeping the absolute expiry recorded when they were issued."""
        await self.repository.save_tokens(self.server_id, tokens.model_dump_json(), expires_at, user_id=self.user_id)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        record = await self.repository.get(self.server_id, user_id=self.user_id)
        if record is None or record.client_info_json is None:
            return None
        return OAuthClientInformationFull.model_validate_json(record.client_info_json)

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        await self.repository.save_client_info(self.server_id, client_info.model_dump_json(), user_id=self.user_id)

    async def get_discovery(self) -> OAuthDiscovery | None:
        record = await self.repository.get(self.server_id, user_id=self.user_id)
        if record is None or record.discovery_json is None:
            return None
        try:
            return OAuthDiscovery.model_validate_json(record.discovery_json)
        except ValidationError:
            logger.warning(f"Ignoring unreadable OAuth discovery stored for server {self.server_id}")
            return None

    async def set_discovery(self, discovery: OAuthDiscovery) -> None:
        await self.repository.save_discovery(self.server_id, discovery.model_dump_json(), user_id=self.user_id)


class HubOAuthClientProvider(OAuthClientProvider):
    """The SDK provider, plus, for a server's stored credentials:
    - tokens keep their expiry, so an expired one is refreshed up front instead of being sent, rejected with 401
      and sent down the full sign-in path;
    - the authorization server metadata found at sign-in is restored, so the refresh goes to the real token endpoint.
    """

    async def _initialize(self) -> None:
        await super()._initialize()
        tokens = self.context.current_tokens
        if tokens is not None and tokens.expires_in is not None:
            self.context.update_token_expiry(tokens)
        storage = self.context.storage
        if isinstance(storage, DbTokenStorage) and self.context.oauth_metadata is None:
            await self._restore_discovery(storage)

    async def _restore_discovery(self, storage: DbTokenStorage) -> None:
        discovery = await storage.get_discovery()
        if discovery is None and self.context.current_tokens is not None:
            # Saved before the discovery was stored: find it once and keep it.
            try:
                discovery = await discover(self.context.server_url)
            except Exception as exc:
                logger.warning(f"OAuth metadata discovery for server {storage.server_id} failed: {exc}")
                return
            if discovery is not None:
                await storage.set_discovery(discovery)
        if discovery is not None:
            discovery.apply_to(self.context)


def callback_url(settings: Settings) -> str:
    """The redirect URI registered with every authorization server."""
    return f"{settings.PUBLIC_API_BASE_URL}{settings.API_V1_STR}/oauth/callback"


def build_client_metadata(settings: Settings, provider: OAuthProvider | None) -> OAuthClientMetadata:
    """Metadata the hub registers itself with: a public web client using the authorization-code grant."""
    return OAuthClientMetadata(
        client_name=OAUTH_CLIENT_NAME,
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


async def discover(server_url: str) -> OAuthDiscovery | None:
    """Find a server's authorization server metadata as the SDK does on a 401: protected resource metadata
    (RFC 9728), then the authorization server's (RFC 8414), checking its issuer. None if the server has none."""
    async with httpx2.AsyncClient(timeout=OAUTH_DISCOVERY_TIMEOUT_SECONDS) as client:
        resource: ProtectedResourceMetadata | None = None
        for url in build_protected_resource_metadata_discovery_urls(None, server_url):
            resource = await handle_protected_resource_response(await client.send(create_oauth_metadata_request(url)))
            if resource is not None:
                break
        auth_server_url = str(resource.authorization_servers[0]) if resource else None
        for url in build_oauth_authorization_server_metadata_discovery_urls(auth_server_url, server_url):
            ok, metadata = await handle_auth_metadata_response(await client.send(create_oauth_metadata_request(url)))
            if not ok:
                break
            if metadata is not None:
                if auth_server_url is not None:
                    validate_metadata_issuer(metadata, auth_server_url)
                return OAuthDiscovery(auth_server_url=auth_server_url, protected_resource_metadata=resource, oauth_metadata=metadata)
    return None


def _expires_at(tokens: OAuthToken) -> float | None:
    return time.time() + int(tokens.expires_in) if tokens.expires_in is not None else None


def _with_remaining_lifetime(tokens: OAuthToken, expires_at: float | None) -> OAuthToken:
    """Stored tokens carry an absolute expiry; the SDK reads a relative `expires_in`."""
    if expires_at is None:
        return tokens
    return tokens.model_copy(update={"expires_in": max(0, int(expires_at - time.time()))})
