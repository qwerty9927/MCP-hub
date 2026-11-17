"""Connecting a hosted MCP server with OAuth, end to end against a real OAuth-protected server (ADR-0008)."""

import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

import app.infrastructure.database as db_module
from app.api.dependencies import get_oauth_service
from app.infrastructure.oauth.provider_catalog import OAuthProvider, OAuthProviderCatalog
from app.main import app
from app.models.server_oauth_credential_model import ServerOAuthCredentialModel
from tests.fake_oauth_server import FakeOAuthMcpServer

PORT = 8931


@pytest.fixture(scope="module")
def oauth_server():
    server = FakeOAuthMcpServer(PORT)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def catalog(oauth_server: FakeOAuthMcpServer):
    """Point the OAuth service at a catalog holding the fake server, plus one provider that needs setup."""
    catalog = OAuthProviderCatalog(
        [
            OAuthProvider(id="fake", name="Fake", description="Test server", category="Testing", mcp_url=oauth_server.mcp_url),
            OAuthProvider(
                id="needs-app",
                name="Needs App",
                description="No dynamic registration",
                category="Testing",
                mcp_url=oauth_server.mcp_url,
                requires_client=True,
            ),
        ]
    )

    def service():
        oauth_service = get_oauth_service()
        oauth_service.catalog = catalog
        return oauth_service

    app.dependency_overrides[get_oauth_service] = service
    yield catalog
    app.dependency_overrides.pop(get_oauth_service, None)


async def sign_in(client: AsyncClient, authorization_url: str) -> httpx.Response:
    """Play the browser: open the authorization URL (auto-approved), then follow the redirect to our callback."""
    async with httpx.AsyncClient() as browser:
        consent = await browser.get(authorization_url, follow_redirects=False)
    assert consent.status_code in (302, 303, 307), consent.text
    query = parse_qs(urlparse(consent.headers["location"]).query)
    return await client.get("/api/v1/oauth/callback", params={"code": query["code"][0], "state": query["state"][0]})


def complete_params(response: httpx.Response) -> dict[str, str]:
    assert response.status_code == 303, response.text
    location = urlparse(response.headers["location"])
    assert location.path == "/oauth/complete"
    return {key: values[0] for key, values in parse_qs(location.query).items()}


async def connect(client: AsyncClient, provider_id: str = "fake", **extra) -> dict[str, str]:
    res = await client.post("/api/v1/oauth/connect", json={"provider_id": provider_id, **extra})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["authorization_url"] and body["state"]
    return complete_params(await sign_in(client, body["authorization_url"]))


async def stored_credentials(server_id: str) -> ServerOAuthCredentialModel:
    async with db_module.async_session_factory() as session:
        result = await session.execute(select(ServerOAuthCredentialModel).where(ServerOAuthCredentialModel.server_id == server_id))
        return result.scalar_one()


async def test_providers_list_marks_unconfigured_ones(async_client: AsyncClient, catalog):
    res = await async_client.get("/api/v1/oauth/providers")
    assert res.status_code == 200
    by_id = {provider["id"]: provider for provider in res.json()}
    assert by_id["fake"]["available"] is True and by_id["fake"]["connected_count"] == 0
    assert by_id["needs-app"]["available"] is False
    assert "OAUTH_CLIENTS" in by_id["needs-app"]["setup_hint"]

    refused = await async_client.post("/api/v1/oauth/connect", json={"provider_id": "needs-app"})
    assert refused.status_code == 400


async def test_providers_require_login(anon_client: AsyncClient, catalog):
    assert (await anon_client.get("/api/v1/oauth/providers")).status_code == 401
    assert (await anon_client.post("/api/v1/oauth/connect", json={"provider_id": "fake"})).status_code == 401


async def test_connect_creates_a_working_server_without_leaking_tokens(async_client: AsyncClient, catalog, oauth_server):
    result = await connect(async_client)
    assert result["status"] == "success", result
    server_id = result["server_id"]

    server = (await async_client.get(f"/api/v1/servers/{server_id}")).json()
    assert server["name"] == "fake"
    assert server["auth_type"] == "oauth" and server["oauth_provider_id"] == "fake"
    assert server["health_status"] == "HEALTHY" and server["discovered_tool_count"] == 1

    # Tokens never appear in the API, and are encrypted at rest.
    access_token = next(iter(oauth_server.provider.access_tokens))
    assert access_token not in str(server)
    stored = await stored_credentials(server_id)
    assert stored.tokens_enc and access_token not in stored.tokens_enc
    assert stored.client_info_enc and "client_id" not in stored.client_info_enc

    # A second connection of the same provider gets its own name.
    second = await connect(async_client)
    assert (await async_client.get(f"/api/v1/servers/{second['server_id']}")).json()["name"] == "fake-2"
    providers = {p["id"]: p for p in (await async_client.get("/api/v1/oauth/providers")).json()}
    assert providers["fake"]["connected_count"] == 2


async def test_hub_reconnects_with_stored_tokens_and_refreshes_expired_ones(async_client: AsyncClient, catalog, oauth_server):
    server_id = (await connect(async_client))["server_id"]
    await async_client.post(f"/api/v1/servers/{server_id}/disconnect")

    # Stored tokens are used as they are while valid.
    refreshes_before = oauth_server.provider.refresh_count
    res = await async_client.post(f"/api/v1/servers/{server_id}/connect")
    assert res.status_code == 200, res.text
    assert oauth_server.provider.refresh_count == refreshes_before

    # An expired access token is refreshed up front and the new one is stored.
    await async_client.post(f"/api/v1/servers/{server_id}/disconnect")
    before = await stored_credentials(server_id)
    async with db_module.async_session_factory() as session:
        model = await session.get(ServerOAuthCredentialModel, server_id)
        model.access_token_expires_at = time.time() - 10
        await session.commit()
    res = await async_client.post(f"/api/v1/servers/{server_id}/connect")
    assert res.status_code == 200, res.text
    assert oauth_server.provider.refresh_count == refreshes_before + 1
    after = await stored_credentials(server_id)
    assert after.tokens_enc != before.tokens_enc
    assert after.access_token_expires_at > time.time()


async def test_revoked_tokens_mark_the_server_needs_auth_and_reconnect_fixes_it(async_client: AsyncClient, catalog, oauth_server):
    server_id = (await connect(async_client))["server_id"]
    await async_client.post(f"/api/v1/servers/{server_id}/disconnect")
    oauth_server.provider.revoke_everything()

    res = await async_client.post(f"/api/v1/servers/{server_id}/connect")
    assert res.status_code == 502
    assert res.json()["error"]["details"]["reason"] == "oauth_reauthorization_required"
    assert (await async_client.get(f"/api/v1/servers/{server_id}")).json()["health_status"] == "NEEDS_AUTH"

    again = await async_client.post(f"/api/v1/servers/{server_id}/oauth/reconnect")
    assert again.status_code == 200, again.text
    result = complete_params(await sign_in(async_client, again.json()["authorization_url"]))
    assert result == {"status": "success", "server_id": server_id}
    server = (await async_client.get(f"/api/v1/servers/{server_id}")).json()
    assert server["health_status"] == "HEALTHY"


async def test_callback_state_is_single_use_and_unknown_state_fails(async_client: AsyncClient, catalog):
    body = (await async_client.post("/api/v1/oauth/connect", json={"provider_id": "fake"})).json()
    async with httpx.AsyncClient() as browser:
        consent = await browser.get(body["authorization_url"], follow_redirects=False)
    query = parse_qs(urlparse(consent.headers["location"]).query)
    params = {"code": query["code"][0], "state": query["state"][0]}

    assert complete_params(await async_client.get("/api/v1/oauth/callback", params=params))["status"] == "success"
    replay = complete_params(await async_client.get("/api/v1/oauth/callback", params=params))
    assert replay["status"] == "error" and "expired" in replay["error"]

    forged = complete_params(await async_client.get("/api/v1/oauth/callback", params={"code": "x", "state": "forged"}))
    assert forged["status"] == "error"


async def test_denied_consent_creates_nothing(async_client: AsyncClient, catalog):
    body = (await async_client.post("/api/v1/oauth/connect", json={"provider_id": "fake"})).json()
    denied = complete_params(await async_client.get("/api/v1/oauth/callback", params={"state": body["state"], "error": "access_denied"}))
    assert denied["status"] == "error" and "access_denied" in denied["error"]
    assert (await async_client.get("/api/v1/servers")).json()["total"] == 0


async def test_reconnect_is_scoped_to_the_owner(async_client: AsyncClient, other_user_client: AsyncClient, catalog):
    server_id = (await connect(async_client))["server_id"]
    assert (await other_user_client.post(f"/api/v1/servers/{server_id}/oauth/reconnect")).status_code == 404


async def test_explicit_name_conflict_is_refused(async_client: AsyncClient, catalog):
    await connect(async_client, name="mine")
    res = await async_client.post("/api/v1/oauth/connect", json={"provider_id": "fake", "name": "mine"})
    assert res.status_code == 409
