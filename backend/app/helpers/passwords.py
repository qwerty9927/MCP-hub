"""Password hashing helpers (argon2id)."""

import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

# Verified against when an account does not exist, so a login attempt costs the same either way.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


async def hash_password_async(password: str) -> str:
    """Hash off the event loop; argon2 is deliberately CPU-expensive."""
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password_hash: str | None, password: str) -> bool:
    """Verify off the event loop; `None` (no such account) still does the work and returns False."""
    result = await asyncio.to_thread(verify_password, password_hash or _DUMMY_HASH, password)
    return result and password_hash is not None
