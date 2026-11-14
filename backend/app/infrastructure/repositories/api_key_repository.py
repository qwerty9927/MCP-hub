"""API key repository interface and PostgreSQL implementation."""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.infrastructure.database as db_module
from app.domain.api_key_entity import ApiKeyEntity
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
    async def list_by_user(self, user_id: UUID) -> list[ApiKeyEntity]:
        """Return the account's keys, newest first, including revoked ones."""

    @abstractmethod
    async def revoke(self, user_id: UUID, key_id: UUID) -> bool:
        """Revoke a key owned by `user_id`; False when there is no such active key."""

    @abstractmethod
    async def touch_last_used(self, key_id: UUID, timestamp: datetime) -> None:
        pass


class PostgresApiKeyRepository(ApiKeyRepositoryAbstract):
    def __init__(self, session_factory: async_sessionmaker | None = None) -> None:
        self._session_factory = session_factory

    @property
    def session_factory(self) -> async_sessionmaker:
        return self._session_factory or db_module.async_session_factory

    @session_factory.setter
    def session_factory(self, factory: async_sessionmaker | None) -> None:
        self._session_factory = factory

    async def create(self, key: ApiKeyEntity) -> ApiKeyEntity:
        async with self.session_factory() as session:
            model = ApiKeyModel.from_domain(key)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model.to_domain()

    async def get_by_hash(self, key_hash: str) -> ApiKeyEntity | None:
        async with self.session_factory() as session:
            result = await session.execute(select(ApiKeyModel).where(ApiKeyModel.key_hash == key_hash))
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None

    async def list_by_user(self, user_id: UUID) -> list[ApiKeyEntity]:
        async with self.session_factory() as session:
            stmt = select(ApiKeyModel).where(ApiKeyModel.user_id == str(user_id)).order_by(ApiKeyModel.created_at.desc())
            result = await session.execute(stmt)
            return [m.to_domain() for m in result.scalars().all()]

    async def revoke(self, user_id: UUID, key_id: UUID) -> bool:
        async with self.session_factory() as session:
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

    async def touch_last_used(self, key_id: UUID, timestamp: datetime) -> None:
        async with self.session_factory() as session:
            await session.execute(update(ApiKeyModel).where(ApiKeyModel.id == str(key_id)).values(last_used_at=timestamp))
            await session.commit()
