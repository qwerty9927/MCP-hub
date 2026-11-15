"""Integration tests for the auth endpoints."""

from httpx import AsyncClient

from app.core.config import get_settings

CREDS = {"email": "erin@example.com", "password": "s3cret-pass"}


async def register_and_login(client: AsyncClient, creds: dict | None = None) -> dict[str, str]:
    creds = creds or CREDS
    assert (await client.post("/api/v1/auth/register", json=creds)).status_code == 201
    res = await client.post("/api/v1/auth/login", json=creds)
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def test_register_login_me(anon_client: AsyncClient):
    headers = await register_and_login(anon_client)

    me = await anon_client.get("/api/v1/auth/me", headers=headers)

    assert me.status_code == 200
    assert me.json()["email"] == CREDS["email"]
    assert "password" not in me.text


async def test_register_validates_input(anon_client: AsyncClient):
    short = await anon_client.post("/api/v1/auth/register", json={"email": "a@b.co", "password": "short"})
    bad_email = await anon_client.post("/api/v1/auth/register", json={"email": "not-an-email", "password": "long-enough-1"})

    assert short.status_code == 422
    assert bad_email.status_code == 422


async def test_duplicate_registration_is_409(anon_client: AsyncClient):
    await register_and_login(anon_client)

    res = await anon_client.post("/api/v1/auth/register", json=CREDS)

    assert res.status_code == 409


async def test_wrong_password_is_401_with_challenge(anon_client: AsyncClient):
    await register_and_login(anon_client)

    res = await anon_client.post("/api/v1/auth/login", json={**CREDS, "password": "wrong-pass"})

    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


async def test_signup_disabled_is_403(anon_client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "ALLOW_SELF_SIGNUP", False)

    res = await anon_client.post("/api/v1/auth/register", json=CREDS)

    assert res.status_code == 403


async def test_me_requires_a_valid_token(anon_client: AsyncClient):
    assert (await anon_client.get("/api/v1/auth/me")).status_code == 401
    assert (await anon_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})).status_code == 401


async def test_api_key_endpoints(anon_client: AsyncClient):
    headers = await register_and_login(anon_client)

    created = await anon_client.post("/api/v1/auth/api-keys", json={"name": "laptop"}, headers=headers)
    assert created.status_code == 201
    key = created.json()["key"]
    assert key.startswith("mhk_")

    listed = await anon_client.get("/api/v1/auth/api-keys", headers=headers)
    assert [k["name"] for k in listed.json()] == ["laptop"]
    assert "key" not in listed.json()[0]

    # API keys authenticate MCP clients, not the REST API.
    assert (await anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {key}"})).status_code == 401

    key_id = created.json()["id"]
    assert (await anon_client.delete(f"/api/v1/auth/api-keys/{key_id}", headers=headers)).status_code == 204
    assert (await anon_client.delete(f"/api/v1/auth/api-keys/{key_id}", headers=headers)).status_code == 404
    assert (await anon_client.post("/api/v1/auth/api-keys", json={"name": ""}, headers=headers)).status_code == 422


async def test_api_key_session_idle_timeout_is_set_and_edited(async_client: AsyncClient, other_user_client: AsyncClient):
    """The Session idle timeout is optional at creation (null = default), bounded, and editable by the owner only."""
    default = await async_client.post("/api/v1/auth/api-keys", json={"name": "default"})
    assert default.status_code == 201
    assert default.json()["session_idle_minutes"] is None

    custom = await async_client.post("/api/v1/auth/api-keys", json={"name": "custom", "session_idle_minutes": 5})
    assert custom.status_code == 201
    key_id = custom.json()["id"]
    assert custom.json()["session_idle_minutes"] == 5

    for invalid in (0, 1441, "soon"):
        res = await async_client.post("/api/v1/auth/api-keys", json={"name": "bad", "session_idle_minutes": invalid})
        assert res.status_code == 422, invalid

    updated = await async_client.patch(f"/api/v1/auth/api-keys/{key_id}", json={"session_idle_minutes": 90})
    assert updated.status_code == 200
    assert updated.json()["session_idle_minutes"] == 90
    listed = {k["id"]: k for k in (await async_client.get("/api/v1/auth/api-keys")).json()}
    assert listed[key_id]["session_idle_minutes"] == 90

    reset = await async_client.patch(f"/api/v1/auth/api-keys/{key_id}", json={"session_idle_minutes": None})
    assert reset.status_code == 200 and reset.json()["session_idle_minutes"] is None

    assert (await async_client.patch(f"/api/v1/auth/api-keys/{key_id}", json={"session_idle_minutes": 0})).status_code == 422
    assert (await async_client.patch(f"/api/v1/auth/api-keys/{key_id}", json={})).status_code == 422

    # Another account's key is not found; so is a revoked one.
    assert (await other_user_client.patch(f"/api/v1/auth/api-keys/{key_id}", json={"session_idle_minutes": 10})).status_code == 404
    assert (await async_client.delete(f"/api/v1/auth/api-keys/{key_id}")).status_code == 204
    assert (await async_client.patch(f"/api/v1/auth/api-keys/{key_id}", json={"session_idle_minutes": 10})).status_code == 404
