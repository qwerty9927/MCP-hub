"""Console refresh tokens (ADR-0009): login cookie, refresh with rotation and reuse detection, expiry, logout."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient

import app.infrastructure.database as db_module
from app.core.config import get_settings
from app.core.constants.auth_constants import CONSOLE_CLIENT_HEADER, CONSOLE_CLIENT_HEADER_VALUE, REFRESH_COOKIE_NAME
from app.core.exceptions import UnauthorizedError
from app.domain.refresh_token_entity import RefreshTokenEntity
from app.helpers.tokens import generate_refresh_token, hash_refresh_token
from app.infrastructure.repositories.api_key_repository import PostgresApiKeyRepository
from app.infrastructure.repositories.refresh_token_repository import PostgresRefreshTokenRepository
from app.infrastructure.repositories.user_repository import PostgresUserRepository
from app.schemas.auth_schema import ApiKeyCreateRequest, LoginRequest, RegisterRequest
from app.services.auth_service import AuthService

CREDS = {"email": "rita@example.com", "password": "s3cret-pass"}
CONSOLE = {CONSOLE_CLIENT_HEADER: CONSOLE_CLIENT_HEADER_VALUE}


@pytest.fixture
def auth() -> AuthService:
    return AuthService(
        user_repository=PostgresUserRepository(),
        api_key_repository=PostgresApiKeyRepository(),
        refresh_token_repository=PostgresRefreshTokenRepository(),
    )


async def login(client: AsyncClient) -> str:
    """Register and log in; returns the access token. The refresh cookie lands in the client's cookie jar."""
    await client.post("/api/v1/auth/register", json=CREDS)
    res = await client.post("/api/v1/auth/login", json=CREDS)
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def refresh(client: AsyncClient, refresh_token: str | None = None):
    if refresh_token is not None:
        client.cookies.clear()
        client.cookies.set(REFRESH_COOKIE_NAME, refresh_token)
    return await client.post("/api/v1/auth/refresh", headers=CONSOLE)


def cookie(client: AsyncClient) -> str:
    return client.cookies[REFRESH_COOKIE_NAME]


async def test_login_sets_an_httponly_refresh_cookie(anon_client: AsyncClient):
    await anon_client.post("/api/v1/auth/register", json=CREDS)
    res = await anon_client.post("/api/v1/auth/login", json=CREDS)

    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"access_token", "token_type", "expires_in"}  # the refresh token is never in the body
    assert body["expires_in"] == get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
    set_cookie = res.headers["set-cookie"]
    assert set_cookie.startswith(f"{REFRESH_COOKIE_NAME}=mhr_")
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert f"SameSite={get_settings().REFRESH_COOKIE_SAMESITE}" in set_cookie
    assert f"Max-Age={get_settings().REFRESH_TOKEN_EXPIRE_DAYS * 86400}" in set_cookie
    assert res.headers["cache-control"] == "no-store"


async def test_refresh_issues_a_working_access_token_and_rotates_the_cookie(anon_client: AsyncClient):
    await login(anon_client)
    first = cookie(anon_client)

    res = await refresh(anon_client)

    assert res.status_code == 200, res.text
    assert cookie(anon_client) != first
    me = await anon_client.get("/api/v1/auth/me", headers=bearer(res.json()["access_token"]))
    assert me.status_code == 200 and me.json()["email"] == CREDS["email"]
    # The rotated token keeps working.
    assert (await refresh(anon_client)).status_code == 200


async def test_refresh_needs_the_console_header_and_a_cookie(anon_client: AsyncClient):
    await login(anon_client)

    no_header = await anon_client.post("/api/v1/auth/refresh")
    assert no_header.status_code == 403  # CSRF check: a cross-site form cannot set the header

    anon_client.cookies.clear()
    no_cookie = await anon_client.post("/api/v1/auth/refresh", headers=CONSOLE)
    assert no_cookie.status_code == 401
    assert no_cookie.headers["www-authenticate"] == "Bearer"

    assert (await refresh(anon_client, "mhr_not-a-real-token")).status_code == 401


async def test_reusing_a_rotated_token_revokes_the_whole_sign_in(anon_client: AsyncClient):
    await login(anon_client)
    stolen = cookie(anon_client)
    assert (await refresh(anon_client)).status_code == 200
    current = cookie(anon_client)

    replay = await refresh(anon_client, stolen)

    assert replay.status_code == 401
    # The legitimate holder's newer token is revoked too: the account must log in again.
    assert (await refresh(anon_client, current)).status_code == 401


async def test_reuse_only_revokes_that_sign_in(anon_client: AsyncClient):
    await login(anon_client)
    laptop = cookie(anon_client)
    assert (await anon_client.post("/api/v1/auth/login", json=CREDS)).status_code == 200
    phone = cookie(anon_client)

    assert (await refresh(anon_client, laptop)).status_code == 200
    assert (await refresh(anon_client, laptop)).status_code == 401  # reuse: the laptop sign-in is revoked

    assert (await refresh(anon_client, phone)).status_code == 200


async def test_logout_revokes_the_refresh_token_and_clears_the_cookie(anon_client: AsyncClient):
    await login(anon_client)
    token = cookie(anon_client)

    res = await anon_client.post("/api/v1/auth/logout", headers=CONSOLE)

    assert res.status_code == 204
    cleared = res.headers["set-cookie"]
    assert cleared.startswith(f"{REFRESH_COOKIE_NAME}=") and "Max-Age=0" in cleared and "Path=/api/v1/auth" in cleared
    assert (await refresh(anon_client, token)).status_code == 401


async def test_logout_always_succeeds_and_needs_the_console_header(anon_client: AsyncClient):
    assert (await anon_client.post("/api/v1/auth/logout", headers=CONSOLE)).status_code == 204  # no cookie
    anon_client.cookies.set(REFRESH_COOKIE_NAME, "mhr_unknown")
    assert (await anon_client.post("/api/v1/auth/logout", headers=CONSOLE)).status_code == 204
    assert (await anon_client.post("/api/v1/auth/logout")).status_code == 403


async def test_refresh_token_is_not_a_bearer_token_and_api_keys_cannot_refresh(anon_client: AsyncClient):
    access = await login(anon_client)
    token = cookie(anon_client)
    key = (await anon_client.post("/api/v1/auth/api-keys", json={"name": "agent"}, headers=bearer(access))).json()["key"]

    assert (await anon_client.get("/api/v1/auth/me", headers=bearer(token))).status_code == 401
    assert (await refresh(anon_client, key)).status_code == 401


async def test_api_keys_still_authenticate_mcp_across_refresh_and_logout(auth: AuthService):
    """The /mcp credential (MCPProxyASGI -> authenticate_api_key) does not depend on the console sign-in."""
    user = await auth.register(RegisterRequest(**CREDS))
    tokens = await auth.login(LoginRequest(**CREDS))
    key = (await auth.create_api_key(user.id, ApiKeyCreateRequest(name="agent"))).key

    rotated = await auth.refresh(tokens.refresh_token)
    await auth.logout(rotated.refresh_token)

    principal = await auth.authenticate_api_key(key)
    assert principal is not None and principal.user_id == user.id and principal.api_key_id is not None
    assert await auth.authenticate_api_key(rotated.refresh_token) is None


async def test_an_expired_refresh_token_is_rejected(auth: AuthService, account_id):
    plaintext, token_hash = generate_refresh_token()
    past = datetime.now(UTC) - timedelta(days=1)
    await PostgresRefreshTokenRepository().create(
        RefreshTokenEntity(user_id=account_id, family_id=uuid4(), token_hash=token_hash, created_at=past, expires_at=past)
    )

    with pytest.raises(UnauthorizedError):
        await auth.refresh(plaintext)
    stored = await PostgresRefreshTokenRepository().get_by_hash(token_hash)
    assert stored is not None and stored.used_at is None and stored.revoked_at is None  # expiry is not reuse


async def test_rotation_slides_the_expiry(auth: AuthService):
    await auth.register(RegisterRequest(**CREDS))
    tokens = await auth.login(LoginRequest(**CREDS))

    rotated = await auth.refresh(tokens.refresh_token)

    successor = await PostgresRefreshTokenRepository().get_by_hash(hash_refresh_token(rotated.refresh_token))
    lifetime = timedelta(days=get_settings().REFRESH_TOKEN_EXPIRE_DAYS)
    assert successor is not None
    assert abs(successor.expires_at - (datetime.now(UTC) + lifetime)) < timedelta(minutes=1)
    assert rotated.refresh_max_age == int(lifetime.total_seconds())


async def test_concurrent_refreshes_of_one_token_rotate_it_once(auth: AuthService):
    """Only one of two simultaneous refreshes wins; the loser looks like reuse, so the sign-in ends.

    This is why the console serialises refreshes across tabs (Web Locks, ADR-0009).
    """
    await auth.register(RegisterRequest(**CREDS))
    tokens = await auth.login(LoginRequest(**CREDS))

    results = await asyncio.gather(auth.refresh(tokens.refresh_token), auth.refresh(tokens.refresh_token), return_exceptions=True)

    winners = [r for r in results if not isinstance(r, BaseException)]
    assert len(winners) == 1
    assert sum(isinstance(r, UnauthorizedError) for r in results) == 1
    with pytest.raises(UnauthorizedError):
        await auth.refresh(winners[0].refresh_token)


async def test_purge_deletes_only_expired_tokens(auth: AuthService, account_id):
    repo = PostgresRefreshTokenRepository()
    now = datetime.now(UTC)
    _, expired_hash = generate_refresh_token()
    _, live_hash = generate_refresh_token()
    await repo.create(
        RefreshTokenEntity(user_id=account_id, family_id=uuid4(), token_hash=expired_hash, expires_at=now - timedelta(seconds=1))
    )
    await repo.create(RefreshTokenEntity(user_id=account_id, family_id=uuid4(), token_hash=live_hash, expires_at=now + timedelta(days=1)))

    assert await auth.purge_expired_refresh_tokens() == 1

    assert await repo.get_by_hash(expired_hash) is None
    assert await repo.get_by_hash(live_hash) is not None


async def test_a_purge_failure_raises_for_the_job_wrapper_to_log(monkeypatch: pytest.MonkeyPatch, auth: AuthService):
    async def broken(_before):
        raise RuntimeError("db down")

    monkeypatch.setattr(auth._refresh_token_repository, "delete_expired", broken)

    with pytest.raises(RuntimeError, match="db down"):
        await auth.purge_expired_refresh_tokens()


async def test_a_refresh_racing_logout_never_leaves_a_live_token(auth: AuthService, monkeypatch: pytest.MonkeyPatch):
    """A rotation and a family revoke on the same sign-in are serialised, so nothing survives the logout.

    Each commit is delayed to hold the rotation's transaction open while logout runs: without the family lock the
    revoke's UPDATE does not see the successor the rotation is inserting, and that successor stays live.
    """
    await auth.register(RegisterRequest(**CREDS))
    tokens = await auth.login(LoginRequest(**CREDS))
    real_factory = db_module.async_session_factory

    def slow_commit_factory():
        session = real_factory()
        real_commit = session.commit

        async def commit():
            await asyncio.sleep(0.2)
            await real_commit()

        session.commit = commit
        return session

    monkeypatch.setattr(db_module, "async_session_factory", slow_commit_factory)

    async def logout_once_rotation_started():
        await asyncio.sleep(0.05)
        await auth.logout(tokens.refresh_token)

    refreshed, _ = await asyncio.gather(auth.refresh(tokens.refresh_token), logout_once_rotation_started(), return_exceptions=True)

    monkeypatch.setattr(db_module, "async_session_factory", real_factory)
    assert not isinstance(refreshed, BaseException), refreshed  # the rotation started first, so it wins
    successor = await PostgresRefreshTokenRepository().get_by_hash(hash_refresh_token(refreshed.refresh_token))
    assert successor is not None and successor.revoked_at is not None
    with pytest.raises(UnauthorizedError):
        await auth.refresh(refreshed.refresh_token)
