"""Accounts, console login tokens, and MCP API keys."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.logging import logger
from app.domain.api_key_entity import ApiKeyEntity
from app.domain.principal_entity import Principal
from app.domain.user_entity import UserEntity
from app.helpers.passwords import hash_password_async, verify_password_async
from app.helpers.tokens import create_access_token, decode_access_token, generate_api_key, hash_api_key, is_api_key
from app.infrastructure.repositories.api_key_repository import ApiKeyRepositoryAbstract
from app.infrastructure.repositories.user_repository import UserRepositoryAbstract
from app.schemas.auth_schema import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

# `last_used_at` is refreshed at most this often, so authenticating does not write on every MCP request.
API_KEY_TOUCH_INTERVAL = timedelta(seconds=60)

_INVALID_CREDENTIALS = "Invalid email or password"


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
    )


class AuthService:
    """Registers accounts, issues console tokens and API keys, and resolves a bearer token to a Principal."""

    def __init__(self, user_repository: UserRepositoryAbstract, api_key_repository: ApiKeyRepositoryAbstract) -> None:
        self._users = user_repository
        self._api_keys = api_key_repository

    async def register(self, data: RegisterRequest) -> UserResponse:
        if not get_settings().ALLOW_SELF_SIGNUP:
            raise ForbiddenError("Self sign-up is disabled on this hub")
        user = UserEntity(email=data.email, password_hash=await hash_password_async(data.password))
        created = await self._users.create(user)
        logger.info(f"Registered account {created.id}")
        return _user_response(created)

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self._users.get_by_email(data.email)
        if not await verify_password_async(user.password_hash if user else None, data.password) or user is None:
            raise UnauthorizedError(_INVALID_CREDENTIALS)
        token, expires_in = create_access_token(user.id)
        return TokenResponse(access_token=token, expires_in=expires_in)

    async def get_user(self, user_id: UUID) -> UserResponse:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UnauthorizedError("Account no longer exists")
        return _user_response(user)

    async def create_api_key(self, user_id: UUID, data: ApiKeyCreateRequest) -> ApiKeyCreatedResponse:
        plaintext, prefix, key_hash = generate_api_key()
        created = await self._api_keys.create(ApiKeyEntity(user_id=user_id, name=data.name.strip(), key_prefix=prefix, key_hash=key_hash))
        logger.info(f"Created API key {created.id} for account {user_id}")
        return ApiKeyCreatedResponse(**_api_key_response(created).model_dump(), key=plaintext)

    async def list_api_keys(self, user_id: UUID) -> list[ApiKeyResponse]:
        return [_api_key_response(k) for k in await self._api_keys.list_by_user(user_id)]

    async def revoke_api_key(self, user_id: UUID, key_id: UUID) -> None:
        if not await self._api_keys.revoke(user_id, key_id):
            raise NotFoundError(f"API key '{key_id}' not found", details={"api_key_id": str(key_id)})
        logger.info(f"Revoked API key {key_id} for account {user_id}")

    async def authenticate_console(self, token: str) -> Principal | None:
        """Resolve a console login token (JWT) only. REST endpoints use this so a leaked MCP key cannot manage the account."""
        user_id = decode_access_token(token)
        return Principal(user_id=user_id) if user_id else None

    async def authenticate(self, token: str) -> Principal | None:
        """Resolve any bearer token: an API key (`mhk_...`) or a console JWT. Used by the /mcp endpoint."""
        if not is_api_key(token):
            return await self.authenticate_console(token)

        key = await self._api_keys.get_by_hash(hash_api_key(token))
        if key is None or key.revoked_at is not None:
            return None
        now = datetime.now(UTC)
        if key.last_used_at is None or now - key.last_used_at > API_KEY_TOUCH_INTERVAL:
            try:
                await self._api_keys.touch_last_used(key.id, now)
            except Exception as exc:
                logger.warning(f"Could not update last_used_at for API key {key.id}: {exc}")
        return Principal(user_id=key.user_id, api_key_id=key.id)
