"""Accounts, console login and refresh tokens (ADR-0009), and MCP API keys."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from jwt import InvalidTokenError

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.logging import logger
from app.domain.api_key_entity import ApiKeyEntity
from app.domain.principal_entity import Principal
from app.domain.refresh_token_entity import RefreshTokenEntity
from app.domain.user_entity import UserEntity
from app.helpers.passwords import hash_password_async, verify_password_async
from app.helpers.session_idle import idle_minutes_to_seconds
from app.helpers.tokens import (
    create_access_token,
    decode_access_token,
    generate_api_key,
    generate_refresh_token,
    hash_api_key,
    hash_refresh_token,
)
from app.infrastructure.repositories.api_key_repository import ApiKeyRepositoryAbstract
from app.infrastructure.repositories.refresh_token_repository import RefreshTokenRepositoryAbstract
from app.infrastructure.repositories.user_repository import UserRepositoryAbstract
from app.schemas.auth_schema import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    ApiKeyUpdateRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

# `last_used_at` is refreshed at most this often, so authenticating does not write on every MCP request.
API_KEY_TOUCH_INTERVAL = timedelta(seconds=60)

_INVALID_CREDENTIALS = "Invalid email or password"
_INVALID_REFRESH = "Invalid or expired refresh token"


@dataclass(frozen=True)
class ConsoleTokens:
    """What a login or refresh hands the console: the access token (response body) and the refresh token (cookie)."""

    access: TokenResponse
    refresh_token: str
    refresh_max_age: int  # seconds until the refresh token expires


class AuthService:
    """Registers accounts, issues console tokens and API keys, and resolves a bearer token to a Principal."""

    def __init__(
        self,
        user_repository: UserRepositoryAbstract,
        api_key_repository: ApiKeyRepositoryAbstract,
        refresh_token_repository: RefreshTokenRepositoryAbstract,
    ) -> None:
        self._user_repository = user_repository
        self._api_key_repository = api_key_repository
        self._refresh_token_repository = refresh_token_repository

    async def register(self, data: RegisterRequest) -> UserResponse:
        if not get_settings().ALLOW_SELF_SIGNUP:
            raise ForbiddenError("Self sign-up is disabled on this hub")
        user = UserEntity(email=data.email, password_hash=await hash_password_async(data.password))
        created = await self._user_repository.create(user)
        logger.info(f"Registered account {created.id}")
        return _user_response(created)

    async def login(self, data: LoginRequest) -> ConsoleTokens:
        """Check the password and start a new sign-in: an access token plus the first refresh token of a new family."""
        user = await self._user_repository.get_by_email(data.email)
        if not await verify_password_async(user.password_hash if user else None, data.password) or user is None:
            raise UnauthorizedError(_INVALID_CREDENTIALS)
        now = datetime.now(UTC)
        plaintext, token_hash = generate_refresh_token()
        await self._refresh_token_repository.create(
            RefreshTokenEntity(
                user_id=user.id,
                family_id=uuid4(),
                token_hash=token_hash,
                created_at=now,
                expires_at=now + _refresh_lifetime(),
            )
        )
        return _console_tokens(user.id, plaintext, now)

    async def refresh(self, refresh_token: str | None) -> ConsoleTokens:
        """Exchange a live refresh token for a new access token and its successor (rotation).

        A token that was already used is a replay, by an attacker or by a client that lost the response: either
        way the whole sign-in is revoked, and the account must log in again.
        """
        if not refresh_token:
            raise UnauthorizedError(_INVALID_REFRESH)
        now = datetime.now(UTC)
        token_hash = hash_refresh_token(refresh_token)
        successor_plaintext, successor_hash = generate_refresh_token()
        successor = await self._refresh_token_repository.rotate(token_hash, successor_hash, now + _refresh_lifetime(), now)
        if successor is not None:
            return _console_tokens(successor.user_id, successor_plaintext, now)

        presented = await self._refresh_token_repository.get_by_hash(token_hash)
        if presented is not None and presented.used_at is not None and presented.revoked_at is None:
            revoked = await self._refresh_token_repository.revoke_family(user_id=presented.user_id, family_id=presented.family_id, now=now)
            logger.warning(
                f"Refresh token reuse for account {presented.user_id}: revoked {revoked} token(s) of sign-in {presented.family_id}"
            )
        raise UnauthorizedError(_INVALID_REFRESH)

    async def logout(self, refresh_token: str | None) -> None:
        """End the sign-in the refresh token belongs to. Unknown or missing tokens are ignored: logout always succeeds."""
        if not refresh_token:
            return
        presented = await self._refresh_token_repository.get_by_hash(hash_refresh_token(refresh_token))
        if presented is None:
            return
        await self._refresh_token_repository.revoke_family(user_id=presented.user_id, family_id=presented.family_id, now=datetime.now(UTC))
        logger.info(f"Signed out sign-in {presented.family_id} of account {presented.user_id}")

    async def purge_expired_refresh_tokens(self) -> int:
        """Delete expired refresh tokens; returns how many. Run by the scheduler, whose logged_job logs a failure."""
        return await self._refresh_token_repository.delete_expired(datetime.now(UTC))

    async def get_user(self, user_id: UUID) -> UserResponse:
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise UnauthorizedError("Account no longer exists")
        return _user_response(user)

    async def create_api_key(self, user_id: UUID, data: ApiKeyCreateRequest) -> ApiKeyCreatedResponse:
        plaintext, prefix, key_hash = generate_api_key()
        created = await self._api_key_repository.create(
            ApiKeyEntity(
                user_id=user_id,
                name=data.name.strip(),
                key_prefix=prefix,
                key_hash=key_hash,
                session_idle_minutes=data.session_idle_minutes,
            )
        )
        logger.info(f"Created API key {created.id} for account {user_id}")
        return ApiKeyCreatedResponse(**_api_key_response(created).model_dump(), key=plaintext)

    async def list_api_keys(self, user_id: UUID) -> list[ApiKeyResponse]:
        return [_api_key_response(k) for k in await self._api_key_repository.list_by_user(user_id)]

    async def update_api_key(self, user_id: UUID, key_id: UUID, data: ApiKeyUpdateRequest) -> ApiKeyResponse:
        """Change a key's Session idle timeout. Sessions already open keep the timeout they started with."""
        updated = await self._api_key_repository.update_session_idle(user_id, key_id, data.session_idle_minutes)
        if updated is None:
            raise NotFoundError(f"API key '{key_id}' not found", details={"api_key_id": str(key_id)})
        logger.info(f"Set session idle timeout of API key {key_id} to {data.session_idle_minutes} min")
        return _api_key_response(updated)

    async def revoke_api_key(self, user_id: UUID, key_id: UUID) -> None:
        if not await self._api_key_repository.revoke(user_id, key_id):
            raise NotFoundError(f"API key '{key_id}' not found", details={"api_key_id": str(key_id)})
        logger.info(f"Revoked API key {key_id} for account {user_id}")

    def authenticate_console(self, token: str) -> Principal | None:
        """Resolve a console login token (JWT) only. REST endpoints use this so a leaked MCP key cannot manage the account."""
        try:
            user_id = decode_access_token(token)

            return Principal(user_id=user_id)
        except InvalidTokenError:
            return None

    async def authenticate_console_user(self, token: str) -> Principal | None:
        """Resolve a console login token whose account still exists. A deleted account's unexpired token gets None."""
        principal = self.authenticate_console(token)
        if principal is None or await self._user_repository.get_by_id(principal.user_id) is None:
            return None
        return principal

    async def authenticate_api_key(self, token: str) -> Principal | None:
        """Resolve an API key (`mhk_...`) to its account; None if unknown or revoked. Used by the /mcp endpoint."""
        key = await self._api_key_repository.get_by_hash(hash_api_key(token))
        if key is None or key.revoked_at is not None:
            return None

        now = datetime.now(UTC)
        if key.last_used_at is None or now - key.last_used_at > API_KEY_TOUCH_INTERVAL:
            try:
                await self._api_key_repository.touch_last_used(key.id, now)
            except Exception as exc:
                logger.warning(f"Could not update last_used_at for API key {key.id}: {exc}")

        return Principal(user_id=key.user_id, api_key_id=key.id, session_idle_seconds=idle_minutes_to_seconds(key.session_idle_minutes))


def _console_tokens(user_id: UUID, refresh_plaintext: str, now: datetime) -> ConsoleTokens:
    access_token, expires_in = create_access_token(user_id, now=now)
    return ConsoleTokens(
        access=TokenResponse(access_token=access_token, expires_in=expires_in),
        refresh_token=refresh_plaintext,
        refresh_max_age=int(_refresh_lifetime().total_seconds()),
    )


def _refresh_lifetime() -> timedelta:
    return timedelta(days=get_settings().REFRESH_TOKEN_EXPIRE_DAYS)


def _user_response(user: UserEntity) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, created_at=user.created_at)


def _api_key_response(key: ApiKeyEntity) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
        revoked_at=key.revoked_at,
        session_idle_minutes=key.session_idle_minutes,
    )
