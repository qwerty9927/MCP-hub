"""Rate limits for the unauthenticated /auth endpoints (login, register, refresh).

Counters live in Postgres, so every hub instance shares them and a restart does not reset them. Attempts are counted
in fixed windows of AUTH_RATE_LIMIT_WINDOW_SECONDS; once a bucket reaches AUTH_RATE_LIMIT_ATTEMPTS, requests get 429.

Login and refresh count only failures (`ensure_allowed` before, `record_failure` after a rejected attempt): users
signing in or refreshing normally, even many behind one address, never use up attempts. Registering counts every
attempt (`check`), since each success creates an account. Concurrent requests can each pass `ensure_allowed` before
any failure is recorded, so a burst may exceed the limit by its own size; argon2 work stays bounded by its pool.
"""

import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.core.exceptions import TooManyRequestsError
from app.infrastructure.repositories.auth_rate_limit_repository import AuthRateLimitRepositoryAbstract


class AuthRateLimiter:
    def __init__(self, repository: AuthRateLimitRepositoryAbstract, settings: Callable[[], Settings]):
        self._repository = repository
        self._settings = settings

    async def check(self, *bucket_keys: str) -> None:
        """Count one attempt against every bucket; raise TooManyRequestsError if any is over its limit.

        Every bucket is counted even when an earlier one is already over, so an attacker spreading attempts over
        many addresses still uses up the per-email bucket.
        """
        settings = self._settings()
        window = settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
        now = datetime.now(UTC)
        retry_after = 0
        for key in bucket_keys:
            attempts, window_started_at = await self._repository.hit(key, window_seconds=window, now=now)
            if attempts > settings.AUTH_RATE_LIMIT_ATTEMPTS:
                remaining = (window_started_at + timedelta(seconds=window) - now).total_seconds()
                retry_after = max(retry_after, math.ceil(remaining), 1)
        if retry_after:
            raise TooManyRequestsError("Too many attempts. Try again later.", retry_after=retry_after)

    async def ensure_allowed(self, *bucket_keys: str) -> None:
        """Raise TooManyRequestsError if any bucket has used up its attempts; counts nothing."""
        settings = self._settings()
        window = settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
        now = datetime.now(UTC)
        retry_after = 0
        for key in bucket_keys:
            attempts, window_started_at = await self._repository.peek(key, window_seconds=window, now=now)
            if window_started_at is not None and attempts >= settings.AUTH_RATE_LIMIT_ATTEMPTS:
                remaining = (window_started_at + timedelta(seconds=window) - now).total_seconds()
                retry_after = max(retry_after, math.ceil(remaining), 1)
        if retry_after:
            raise TooManyRequestsError("Too many failed attempts. Try again later.", retry_after=retry_after)

    async def record_failure(self, *bucket_keys: str) -> None:
        """Count one failed attempt against every bucket."""
        window = self._settings().AUTH_RATE_LIMIT_WINDOW_SECONDS
        now = datetime.now(UTC)
        for key in bucket_keys:
            await self._repository.hit(key, window_seconds=window, now=now)

    async def purge_stale(self) -> int:
        """Delete counters whose window is over (scheduled job); returns how many."""
        window = self._settings().AUTH_RATE_LIMIT_WINDOW_SECONDS
        return await self._repository.delete_stale(before=datetime.now(UTC) - timedelta(seconds=window))
