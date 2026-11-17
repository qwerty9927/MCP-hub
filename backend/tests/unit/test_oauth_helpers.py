"""Unit tests for the OAuth building blocks (ADR-0008)."""

import time

import pytest
from cryptography.fernet import Fernet
from mcp.client.auth import OAuthFlowError
from mcp.shared.auth import OAuthToken

from app.core.config import get_settings
from app.helpers.crypto import SecretCipher
from app.infrastructure.oauth.client_provider import (
    HubOAuthClientProvider,
    MemoryTokenStorage,
    build_client_metadata,
    callback_url,
    find_oauth_error,
    preregistered_client,
)
from app.infrastructure.oauth.provider_catalog import OAuthProvider, OAuthProviderCatalog, get_provider_catalog


def provider(**overrides) -> OAuthProvider:
    return OAuthProvider(
        **{"id": "acme", "name": "Acme", "description": "d", "category": "c", "mcp_url": "https://mcp.acme.test/mcp", **overrides}
    )


def test_cipher_round_trip_and_wrong_key():
    cipher = SecretCipher(Fernet.generate_key().decode())
    secret = cipher.encrypt('{"access_token": "abc"}')
    assert "abc" not in secret
    assert cipher.decrypt(secret) == '{"access_token": "abc"}'
    with pytest.raises(ValueError):
        SecretCipher(Fernet.generate_key().decode()).decrypt(secret)


def test_shipped_catalog_loads_with_unique_ids():
    providers = get_provider_catalog().list()
    assert len(providers) >= 8
    assert all(p.mcp_url.startswith("https://") for p in providers)


def test_catalog_rejects_duplicate_ids():
    with pytest.raises(ValueError):
        OAuthProviderCatalog([provider(), provider()])


def test_client_metadata_is_a_public_web_client_on_our_callback():
    settings = get_settings()
    metadata = build_client_metadata(settings, provider(scopes="read"))
    assert [str(uri) for uri in metadata.redirect_uris] == [callback_url(settings)]
    assert metadata.token_endpoint_auth_method == "none"
    assert metadata.scope == "read"
    assert callback_url(settings).endswith("/api/v1/oauth/callback")


def test_preregistered_client_comes_from_settings():
    settings = get_settings().model_copy(update={"OAUTH_CLIENTS": {"acme": {"client_id": "id-1", "client_secret": "s"}}})
    client = preregistered_client(settings, provider())
    assert client and client.client_id == "id-1" and client.token_endpoint_auth_method == "client_secret_post"
    assert preregistered_client(settings, provider(id="other")) is None


async def test_stored_tokens_keep_their_remaining_lifetime():
    storage = MemoryTokenStorage()
    await storage.set_tokens(OAuthToken(access_token="a", expires_in=3600))
    storage.expires_at = time.time() - 5  # pretend it expired while stored
    loaded = await storage.get_tokens()
    assert loaded and loaded.expires_in == 0


async def test_provider_treats_a_stored_expired_token_as_expired():
    storage = MemoryTokenStorage()
    await storage.set_tokens(OAuthToken(access_token="a", expires_in=3600, refresh_token="r"))
    storage.expires_at = time.time() - 5
    auth = HubOAuthClientProvider("https://mcp.acme.test/mcp", build_client_metadata(get_settings(), None), storage)
    await auth._initialize()
    assert auth.context.is_token_valid() is False


def test_find_oauth_error_looks_through_groups_and_causes():
    inner = OAuthFlowError("refresh failed")
    try:
        try:
            raise inner
        except OAuthFlowError as exc:
            raise RuntimeError("transport closed") from exc
    except RuntimeError as wrapped:
        group = ExceptionGroup("task group", [ValueError("other"), wrapped])
    assert find_oauth_error(group) is inner
    assert find_oauth_error(RuntimeError("plain")) is None
    assert find_oauth_error(None) is None
