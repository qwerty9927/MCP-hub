"""Assigns rows created before accounts existed to an owner."""

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.infrastructure.database as db_module
from app.models.server_model import ServerModel
from app.models.session_model import SessionModel
from app.models.tool_model import ToolModel


class OwnershipRepositoryAbstract(ABC):
    @abstractmethod
    async def claim_unowned(self, owner_id: UUID) -> int:
        """Give every unowned Server, Tool and Session to `owner_id`; returns the number of Servers claimed."""


class PostgresOwnershipRepository(OwnershipRepositoryAbstract):
    def __init__(self, session_factory: async_sessionmaker | None = None) -> None:
        self._session_factory = session_factory

    @property
    def session_factory(self) -> async_sessionmaker:
        return self._session_factory or db_module.async_session_factory

    @session_factory.setter
    def session_factory(self, factory: async_sessionmaker | None) -> None:
        self._session_factory = factory

    async def claim_unowned(self, owner_id: UUID) -> int:
        owner = str(owner_id)
        async with self.session_factory() as session:
            servers = await session.execute(update(ServerModel).where(ServerModel.owner_id.is_(None)).values(owner_id=owner))
            await session.execute(update(ToolModel).where(ToolModel.owner_id.is_(None)).values(owner_id=owner))
            await session.execute(update(SessionModel).where(SessionModel.owner_id.is_(None)).values(owner_id=owner))
            await session.commit()
            return servers.rowcount
