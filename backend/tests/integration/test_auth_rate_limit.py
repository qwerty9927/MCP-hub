"""Rate limiting of the unauthenticated /auth endpoints: login, register and refresh."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app

LIMIT = 3
CREDS = {"email": "limited@test.local", "password": "test-password-123"}
CONSOLE = {"X-MCP-Hub-Client": "console"}


@pytest.fixture(autouse=True)
def small_limit(monkeypatch):
    monkeypatch.setattr(get_settings(), "AUTH_RATE_LIMIT_ATTEMPTS", LIMIT)
    monkeypatch.setattr(get_settings(), "AUTH_RATE_LIMIT_WINDOW_SECONDS", 300)


def _client(ip: str) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app, client=(ip, 50000)), base_url="http://testserver")


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with _client("203.0.113.10") as c:
        yield c


def _assert_limited(res) -> None:
    assert res.status_code == 429, res.text
    assert int(res.headers["Retry-After"]) > 0
    assert res.json()["error"]["code"] == "429"


async def test_login_is_limited_per_ip(client: AsyncClient):
    for i in range(LIMIT):
        res = await client.post("/api/v1/auth/login", json={"email": f"nobody{i}@test.local", "password": "wrong-password"})
        assert res.status_code == 401

    _assert_limited(await client.post("/api/v1/auth/login", json={"email": "other@test.local", "password": "wrong-password"}))


async def test_login_is_limited_per_email_across_ips():
    """Spreading guesses over many addresses does not get more attempts at one account."""
    for i in range(LIMIT):
        async with _client(f"198.51.100.{i + 1}") as c:
            res = await c.post("/api/v1/auth/login", json={**CREDS, "password": "wrong-password"})
            assert res.status_code == 401

    async with _client("198.51.100.200") as c:
        _assert_limited(await c.post("/api/v1/auth/login", json={**CREDS, "password": "wrong-password"}))
        # The email bucket is case-insensitive, as sign-in is
        _assert_limited(await c.post("/api/v1/auth/login", json={**CREDS, "email": CREDS["email"].upper()}))


async def test_register_is_limited_per_ip(client: AsyncClient):
    for i in range(LIMIT):
        res = await client.post("/api/v1/auth/register", json={"email": f"new{i}@test.local", "password": "test-password-123"})
        assert res.status_code == 201

    _assert_limited(await client.post("/api/v1/auth/register", json={"email": "one-more@test.local", "password": "test-password-123"}))


async def test_refresh_is_limited_per_ip(client: AsyncClient):
    for _ in range(LIMIT):
        assert (await client.post("/api/v1/auth/refresh", headers=CONSOLE)).status_code == 401

    _assert_limited(await client.post("/api/v1/auth/refresh", headers=CONSOLE))


async def test_limits_are_per_endpoint(client: AsyncClient):
    """Using up the login attempts does not block registering."""
    for _ in range(LIMIT + 1):
        await client.post("/api/v1/auth/login", json={**CREDS, "password": "wrong-password"})

    res = await client.post("/api/v1/auth/register", json={"email": "fresh@test.local", "password": "test-password-123"})
    assert res.status_code == 201


async def test_window_resets():
    """A bucket whose window has passed starts counting again from one."""
    from app.infrastructure.repositories.auth_rate_limit_repository import PostgresAuthRateLimitRepository

    repo = PostgresAuthRateLimitRepository()
    start = datetime.now(UTC)
    for expected in (1, 2, 3):
        attempts, window_started_at = await repo.hit("test:bucket", window_seconds=60, now=start)
        assert attempts == expected
        assert window_started_at == start

    later = start + timedelta(seconds=61)
    attempts, window_started_at = await repo.hit("test:bucket", window_seconds=60, now=later)
    assert attempts == 1
    assert window_started_at == later


async def test_purge_deletes_only_finished_windows():
    from app.infrastructure.repositories.auth_rate_limit_repository import PostgresAuthRateLimitRepository

    repo = PostgresAuthRateLimitRepository()
    now = datetime.now(UTC)
    await repo.hit("test:old", window_seconds=60, now=now - timedelta(seconds=120))
    await repo.hit("test:current", window_seconds=60, now=now)

    assert await repo.delete_stale(before=now - timedelta(seconds=60)) == 1
    attempts, _ = await repo.hit("test:current", window_seconds=60, now=now)
    assert attempts == 2


async def test_successful_logins_do_not_count(client: AsyncClient):
    """Only failed sign-ins use up attempts: a user signing in often, or many users behind one address, is not locked out."""
    await client.post("/api/v1/auth/register", json=CREDS)
    for _ in range(LIMIT + 2):
        assert (await client.post("/api/v1/auth/login", json=CREDS)).status_code == 200


async def test_successful_refreshes_do_not_count(client: AsyncClient):
    """The console refreshes on every token expiry and in every tab; only failed refreshes count."""
    await client.post("/api/v1/auth/register", json=CREDS)
    assert (await client.post("/api/v1/auth/login", json=CREDS)).status_code == 200
    for _ in range(LIMIT + 2):
        assert (await client.post("/api/v1/auth/refresh", headers=CONSOLE)).status_code == 200


async def test_failed_logins_block_even_the_right_password(client: AsyncClient):
    """Once a bucket is over its limit, the request is refused before the password is checked."""
    await client.post("/api/v1/auth/register", json=CREDS)
    for _ in range(LIMIT):
        assert (await client.post("/api/v1/auth/login", json={**CREDS, "password": "wrong-password"})).status_code == 401
    _assert_limited(await client.post("/api/v1/auth/login", json=CREDS))
