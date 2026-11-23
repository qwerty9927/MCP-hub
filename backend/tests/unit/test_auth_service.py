"""Unit tests for accounts, console tokens, and API keys."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from jwt.exceptions import InvalidTokenError

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.helpers.passwords import hash_password, verify_password
from app.helpers.tokens import JWT_ALGORITHM, JWT_AUDIENCE, create_access_token, decode_access_token, generate_api_key, hash_api_key
from app.infrastructure.repositories.api_key_repository import PostgresApiKeyRepository
from app.infrastructure.repositories.refresh_token_repository import PostgresRefreshTokenRepository
from app.infrastructure.repositories.user_repository import PostgresUserRepository
from app.schemas.auth_schema import ApiKeyCreateRequest, LoginRequest, RegisterRequest
from app.services.auth_service import AuthService


@pytest.fixture
def auth() -> AuthService:
    return AuthService(
        user_repository=PostgresUserRepository(),
        api_key_repository=PostgresApiKeyRepository(),
        refresh_token_repository=PostgresRefreshTokenRepository(),
    )


def test_password_hash_roundtrip():
    hashed = hash_password("correct horse")
    assert hashed != "correct horse"
    assert verify_password(hashed, "correct horse")
    assert not verify_password(hashed, "wrong horse")
    assert not verify_password("not-a-hash", "anything")


def test_access_token_roundtrip():
    user_id = uuid4()
    token, expires_in = create_access_token(user_id)

    assert expires_in == get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert decode_access_token(token) == user_id


def test_expired_and_foreign_tokens_are_rejected():
    settings = get_settings()
    user_id = uuid4()
    past = datetime.now(UTC) - timedelta(hours=2)
    expired, _ = create_access_token(user_id, now=past)
    wrong_secret = jwt.encode(
        {"sub": str(user_id), "aud": JWT_AUDIENCE, "exp": datetime.now(UTC) + timedelta(hours=1)},
        "x" * 40,
        algorithm=JWT_ALGORITHM,
    )
    wrong_audience = jwt.encode(
        {"sub": str(user_id), "aud": "someone-else", "exp": datetime.now(UTC) + timedelta(hours=1)},
        settings.JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    unsigned = jwt.encode({"sub": str(user_id), "aud": JWT_AUDIENCE}, None, algorithm="none")

    for token in (expired, wrong_secret, wrong_audience, unsigned, "garbage"):
        with pytest.raises(InvalidTokenError):
            decode_access_token(token)


def test_generated_api_keys_are_unique_and_hashed():
    key, prefix, key_hash = generate_api_key()
    other, _, _ = generate_api_key()

    assert key.startswith("mhk_") and key != other
    assert key.startswith(prefix) and len(prefix) < len(key)
    assert key_hash == hash_api_key(key) and key not in key_hash


async def test_register_and_login(auth: AuthService):
    user = await auth.register(RegisterRequest(email="  Alice@Example.COM ", password="s3cret-pass"))
    assert user.email == "alice@example.com"

    tokens = await auth.login(LoginRequest(email="alice@example.com", password="s3cret-pass"))
    principal = auth.authenticate_console(tokens.access.access_token)
    assert principal is not None and principal.user_id == user.id and principal.api_key_id is None


async def test_duplicate_email_is_a_conflict(auth: AuthService):
    await auth.register(RegisterRequest(email="dup@example.com", password="s3cret-pass"))

    with pytest.raises(ConflictError):
        await auth.register(RegisterRequest(email="DUP@example.com", password="another-pass"))


async def test_bad_credentials_give_one_indistinguishable_error(auth: AuthService):
    await auth.register(RegisterRequest(email="bob@example.com", password="s3cret-pass"))

    with pytest.raises(UnauthorizedError) as wrong_password:
        await auth.login(LoginRequest(email="bob@example.com", password="nope-nope"))
    with pytest.raises(UnauthorizedError) as unknown_user:
        await auth.login(LoginRequest(email="nobody@example.com", password="s3cret-pass"))
    assert wrong_password.value.message == unknown_user.value.message


async def test_signup_can_be_disabled(auth: AuthService, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(get_settings(), "ALLOW_SELF_SIGNUP", False)

    with pytest.raises(ForbiddenError):
        await auth.register(RegisterRequest(email="late@example.com", password="s3cret-pass"))


async def test_api_key_lifecycle(auth: AuthService):
    user = await auth.register(RegisterRequest(email="carol@example.com", password="s3cret-pass"))
    created = await auth.create_api_key(user.id, ApiKeyCreateRequest(name="laptop"))

    listed = await auth.list_api_keys(user.id)
    assert [k.id for k in listed] == [created.id]
    assert not hasattr(listed[0], "key")

    principal = await auth.authenticate_api_key(created.key)
    assert principal is not None and principal.user_id == user.id and principal.api_key_id == created.id
    assert (await auth.list_api_keys(user.id))[0].last_used_at is not None
    # An API key is not a console token: it must not open the REST API.
    assert auth.authenticate_console(created.key) is None

    await auth.revoke_api_key(user.id, created.id)
    assert await auth.authenticate_api_key(created.key) is None
    with pytest.raises(NotFoundError):
        await auth.revoke_api_key(user.id, created.id)


async def test_api_key_belongs_to_its_owner(auth: AuthService):
    owner = await auth.register(RegisterRequest(email="owner@example.com", password="s3cret-pass"))
    other = await auth.register(RegisterRequest(email="other@example.com", password="s3cret-pass"))
    created = await auth.create_api_key(owner.id, ApiKeyCreateRequest(name="mine"))

    with pytest.raises(NotFoundError):
        await auth.revoke_api_key(other.id, created.id)
    assert await auth.authenticate_api_key(created.key) is not None
    assert await auth.list_api_keys(other.id) == []


async def test_unknown_api_key_and_console_token_are_rejected_for_mcp(auth: AuthService):
    assert await auth.authenticate_api_key("mhk_does-not-exist") is None

    # /mcp accepts API keys only: a console login token must not authenticate there.
    user = await auth.register(RegisterRequest(email="dave@example.com", password="s3cret-pass"))
    token, _ = create_access_token(user.id)
    assert await auth.authenticate_api_key(token) is None
