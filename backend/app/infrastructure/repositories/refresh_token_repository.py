"""Console refresh token repository interface and PostgreSQL implementation (ADR-0009)."""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.infrastructure.database as db_module
from app.domain.refresh_token_entity import RefreshTokenEntity
from app.infrastructure.database import Database
from app.models.refresh_token_model import RefreshTokenModel


class RefreshTokenRepositoryAbstract(ABC):
    """Persistence operations for console refresh tokens. Tokens are looked up by hash: the token names its owner."""

    @abstractmethod
    async def create(self, token: RefreshTokenEntity) -> RefreshTokenEntity:
        pass

    @abstractmethod
    async def get_by_hash(self, token_hash: str) -> RefreshTokenEntity | None:
        pass

    @abstractmethod
    async def rotate(
        self, token_hash: str, successor_hash: str, successor_expires_at: datetime, now: datetime
    ) -> RefreshTokenEntity | None:
        """Mark a live token used and store its successor in the same family, in one transaction.

        Returns the successor, or None when the token is unknown, already used, revoked or expired. Of two
        concurrent rotations of one token only one succeeds.
        """

    @abstractmethod
    async def revoke_family(self, *, user_id: UUID, family_id: UUID, now: datetime) -> int:
        """Revoke every token of `user_id`'s sign-in `family_id` not already revoked; returns how many."""

    @abstractmethod
    async def delete_expired(self, before: datetime) -> int:
        """Delete tokens that expired before `before`; returns how many."""


class PostgresRefreshTokenRepository(RefreshTokenRepositoryAbstract):
    def __init__(self, database: Database | None = None) -> None:
        self._database = database or db_module.database

    async def create(self, token: RefreshTokenEntity) -> RefreshTokenEntity:
        async with self._database.session() as session:
            model = RefreshTokenModel.from_domain(token)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model.to_domain()

    async def get_by_hash(self, token_hash: str) -> RefreshTokenEntity | None:
        async with self._database.session() as session:
            result = await session.execute(select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash))
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None

    async def rotate(
        self, token_hash: str, successor_hash: str, successor_expires_at: datetime, now: datetime
    ) -> RefreshTokenEntity | None:
        async with self._database.session() as session:
            family_id = (
                await session.execute(select(RefreshTokenModel.family_id).where(RefreshTokenModel.token_hash == token_hash))
            ).scalar_one_or_none()
            if family_id is None:
                return None
            # Serialise with revoke_family: a logout running alongside would otherwise miss the successor inserted here.
            await _lock_family(session, family_id)
            # The conditional UPDATE decides the winner: a concurrent rotation of the same token matches no row.
            stmt = (
                update(RefreshTokenModel)
                .where(
                    RefreshTokenModel.token_hash == token_hash,
                    RefreshTokenModel.used_at.is_(None),
                    RefreshTokenModel.revoked_at.is_(None),
                    RefreshTokenModel.expires_at > now,
                )
                .values(used_at=now)
                .returning(RefreshTokenModel.user_id, RefreshTokenModel.family_id)
            )
            row = (await session.execute(stmt)).one_or_none()
            if row is None:
                await session.rollback()
                return None
            successor = RefreshTokenModel(
                id=str(uuid4()),
                user_id=row.user_id,
                family_id=row.family_id,
                token_hash=successor_hash,
                created_at=now,
                expires_at=successor_expires_at,
            )
            session.add(successor)
            await session.commit()
            await session.refresh(successor)
            return successor.to_domain()

    async def revoke_family(self, *, user_id: UUID, family_id: UUID, now: datetime) -> int:
        async with self._database.session() as session:
            # Waits for a rotation in progress, so its successor is committed (and revoked here) or never written.
            await _lock_family(session, str(family_id))
            stmt = (
                update(RefreshTokenModel)
                .where(
                    RefreshTokenModel.user_id == str(user_id),
                    RefreshTokenModel.family_id == str(family_id),
                    RefreshTokenModel.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def delete_expired(self, before: datetime) -> int:
        async with self._database.session() as session:
            result = await session.execute(delete(RefreshTokenModel).where(RefreshTokenModel.expires_at < before))
            await session.commit()
            return result.rowcount


async def _lock_family(session: AsyncSession, family_id: str) -> None:
    """Take a transaction-scoped advisory lock on one sign-in family; released at commit or rollback."""
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(family_id, 0))))
