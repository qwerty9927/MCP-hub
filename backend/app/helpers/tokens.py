"""Console JWTs and MCP API key helpers."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import get_settings

JWT_ALGORITHM = "HS256"
JWT_AUDIENCE = "mcp-hub"
API_KEY_PREFIX = "mhk_"
_API_KEY_DISPLAY_PREFIX_LENGTH = len(API_KEY_PREFIX) + 4


def create_access_token(user_id: UUID, now: datetime | None = None) -> tuple[str, int]:
    """Sign a console login token for `user_id`; returns (token, lifetime in seconds)."""
    settings = get_settings()
    issued_at = now or datetime.now(UTC)
    lifetime = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    claims = {
        "sub": str(user_id),
        "aud": JWT_AUDIENCE,
        "iat": issued_at,
        "exp": issued_at + lifetime,
    }
    return jwt.encode(claims, settings.JWT_SECRET, algorithm=JWT_ALGORITHM), int(lifetime.total_seconds())


def decode_access_token(token: str) -> UUID:
    """Return the account a valid, unexpired console token belongs to, or None."""
    claims = jwt.decode(
        token,
        get_settings().JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        audience=JWT_AUDIENCE,
        options={"require": ["exp", "sub", "aud"]},
    )

    return UUID(claims["sub"])


def generate_api_key() -> tuple[str, str, str]:
    """Create a key; returns (plaintext, display prefix, sha256 hash). Only the hash is stored."""
    plaintext = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    return plaintext, plaintext[:_API_KEY_DISPLAY_PREFIX_LENGTH], hash_api_key(plaintext)


def hash_api_key(key: str) -> str:
    # A fast hash is right here: keys are 256 bits of randomness, not human-chosen secrets.
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def is_api_key(token: str) -> bool:
    return token.startswith(API_KEY_PREFIX)
