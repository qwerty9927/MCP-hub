"""API key repository interface and PostgreSQL implementation."""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update

import app.infrastructure.database as db_module
from app.domain.api_key_entity import ApiKeyEntity
from app.infrastructure.database import Database
from app.models.api_key_model import ApiKeyModel


class ApiKeyRepositoryAbstract(ABC):
    """Persistence operations for API keys."""

    @abstractmethod
    async def create(self, key: ApiKeyEntity) -> ApiKeyEntity:
        pass

    @abstractmethod
    async def get_by_hash(self, key_hash: str) -> ApiKeyEntity | None:
        pass

    @abstractmethod
    async def get_active(self, user_id: UUID, key_id: UUID) -> ApiKeyEntity | None:
        """The owner's key, unless revoked; None for another account's key or an unknown one."""
        pass

    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> list[ApiKeyEntity]:
        """Return the account's keys, newest first, including revoked ones."""

    @abstractmethod
    async def revoke(self, user_id: UUID, key_id: UUID) -> bool:
        """Revoke a key owned by `user_id`; False when there is no such active key."""

    @abstractmethod
    async def update_session_idle(self, user_id: UUID, key_id: UUID, session_idle_minutes: int | None) -> ApiKeyEntity | None:
        """Set the Session idle timeout of a key owned by `user_id`; None when there is no such active key."""

    @abstractmethod
    async def touch_last_used(self, key_id: UUID, timestamp: datetime) -> None:
        pass


class PostgresApiKeyRepository(ApiKeyRepositoryAbstract):
    def __init__(self, database: Database | None = None) -> None:
        self._database = database or db_module.database

    async def create(self, key: ApiKeyEntity) -> ApiKeyEntity:
        async with self._database.session() as session:
            model = ApiKeyModel.from_domain(key)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model.to_domain()

    async def get_by_hash(self, key_hash: str) -> ApiKeyEntity | None:
        async with self._database.session() as session:
            result = await session.execute(select(ApiKeyModel).where(ApiKeyModel.key_hash == key_hash))
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None

    async def get_active(self, user_id: UUID, key_id: UUID) -> ApiKeyEntity | None:
        async with self._database.session() as session:
            stmt = select(ApiKeyModel).where(
                ApiKeyModel.id == str(key_id),
                ApiKeyModel.user_id == str(user_id),
                ApiKeyModel.revoked_at.is_(None),
            )
            model = (await session.execute(stmt)).scalar_one_or_none()
            return model.to_domain() if model else None

    async def list_by_user(self, user_id: UUID) -> list[ApiKeyEntity]:
        async with self._database.session() as session:
            stmt = select(ApiKeyModel).where(ApiKeyModel.user_id == str(user_id)).order_by(ApiKeyModel.created_at.desc())
            result = await session.execute(stmt)
            return [model.to_domain() for model in result.scalars().all()]

    async def revoke(self, user_id: UUID, key_id: UUID) -> bool:
        async with self._database.session() as session:
            stmt = (
                update(ApiKeyModel)
                .where(
                    ApiKeyModel.id == str(key_id),
                    ApiKeyModel.user_id == str(user_id),
                    ApiKeyModel.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(UTC))
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def update_session_idle(self, user_id: UUID, key_id: UUID, session_idle_minutes: int | None) -> ApiKeyEntity | None:
        async with self._database.session() as session:
            stmt = (
                update(ApiKeyModel)
                .where(
                    ApiKeyModel.id == str(key_id),
                    ApiKeyModel.user_id == str(user_id),
                    ApiKeyModel.revoked_at.is_(None),
                )
                .values(session_idle_minutes=session_idle_minutes)
                .returning(ApiKeyModel)
            )
            model = (await session.execute(stmt)).scalar_one_or_none()
            await session.commit()
            return model.to_domain() if model else None

    async def touch_last_used(self, key_id: UUID, timestamp: datetime) -> None:
        async with self._database.session() as session:
            await session.execute(update(ApiKeyModel).where(ApiKeyModel.id == str(key_id)).values(last_used_at=timestamp))
            await session.commit()
