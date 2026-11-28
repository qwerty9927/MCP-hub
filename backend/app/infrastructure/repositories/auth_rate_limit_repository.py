"""Auth rate limit repository interface and PostgreSQL implementation: fixed-window attempt counters."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from sqlalchemy import case, delete, select
from sqlalchemy.dialects.postgresql import insert

import app.infrastructure.database as db_module
from app.models.auth_rate_limit_model import AuthRateLimitModel


class AuthRateLimitRepositoryAbstract(ABC):
    """Counts attempts per bucket in fixed windows. A bucket is any string, such as `login:email:<email>`."""

    @abstractmethod
    async def hit(self, bucket_key: str, *, window_seconds: int, now: datetime) -> tuple[int, datetime]:
        """Count one attempt and return (attempts in the current window, when that window started).

        A bucket whose window is over starts a new one at `now`. Concurrent hits on one bucket are all counted.
        """

    @abstractmethod
    async def peek(self, bucket_key: str, *, window_seconds: int, now: datetime) -> tuple[int, datetime | None]:
        """(attempts in the current window, when it started) without counting one; (0, None) when there is none."""

    @abstractmethod
    async def delete_stale(self, before: datetime) -> int:
        """Delete buckets whose window started before `before`; returns how many."""


class PostgresAuthRateLimitRepository(AuthRateLimitRepositoryAbstract):
    async def hit(self, bucket_key: str, *, window_seconds: int, now: datetime) -> tuple[int, datetime]:
        window_over = AuthRateLimitModel.window_started_at <= now - timedelta(seconds=window_seconds)
        statement = insert(AuthRateLimitModel).values(bucket_key=bucket_key, window_started_at=now, attempts=1)
        statement = statement.on_conflict_do_update(
            index_elements=[AuthRateLimitModel.bucket_key],
            set_={
                "attempts": case((window_over, 1), else_=AuthRateLimitModel.attempts + 1),
                "window_started_at": case((window_over, now), else_=AuthRateLimitModel.window_started_at),
            },
        ).returning(AuthRateLimitModel.attempts, AuthRateLimitModel.window_started_at)

        async with db_module.async_session_factory() as session:
            row = (await session.execute(statement)).one()
            await session.commit()
            return row.attempts, row.window_started_at

    async def peek(self, bucket_key: str, *, window_seconds: int, now: datetime) -> tuple[int, datetime | None]:
        statement = select(AuthRateLimitModel.attempts, AuthRateLimitModel.window_started_at).where(
            AuthRateLimitModel.bucket_key == bucket_key,
            AuthRateLimitModel.window_started_at > now - timedelta(seconds=window_seconds),
        )
        async with db_module.async_session_factory() as session:
            row = (await session.execute(statement)).one_or_none()
            return (row.attempts, row.window_started_at) if row else (0, None)

    async def delete_stale(self, before: datetime) -> int:
        async with db_module.async_session_factory() as session:
            result = await session.execute(delete(AuthRateLimitModel).where(AuthRateLimitModel.window_started_at < before))
            await session.commit()
            return result.rowcount or 0
