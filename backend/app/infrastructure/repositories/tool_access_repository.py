"""Which tools each API key may see and run (ADR-0007). Only hidden tools are stored; everything else is visible."""

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

import app.infrastructure.database as db_module
from app.infrastructure.database import Database
from app.models.api_key_disabled_tool_model import ApiKeyDisabledToolModel


class ToolAccessRepositoryAbstract(ABC):
    """Per-API-key tool visibility, keyed by server and tool name."""

    @abstractmethod
    async def disabled_tool_names(self, api_key_id: UUID, server_id: UUID) -> set[str]:
        """Names of the server's tools hidden from the key."""

    @abstractmethod
    async def is_disabled(self, api_key_id: UUID, server_id: UUID, tool_name: str) -> bool:
        """Whether the tool is hidden from the key."""

    @abstractmethod
    async def set_enabled(self, api_key_id: UUID, server_id: UUID, tool_name: str, enabled: bool) -> None:
        """Show (enabled) or hide the tool for the key. Idempotent."""


class PostgresToolAccessRepository(ToolAccessRepositoryAbstract):
    def __init__(self, database: Database | None = None) -> None:
        self._database = database or db_module.database

    async def disabled_tool_names(self, api_key_id: UUID, server_id: UUID) -> set[str]:
        async with self._database.session() as session:
            stmt = select(ApiKeyDisabledToolModel.tool_name).where(
                ApiKeyDisabledToolModel.api_key_id == str(api_key_id),
                ApiKeyDisabledToolModel.server_id == str(server_id),
            )
            return set((await session.execute(stmt)).scalars())

    async def is_disabled(self, api_key_id: UUID, server_id: UUID, tool_name: str) -> bool:
        async with self._database.session() as session:
            stmt = select(ApiKeyDisabledToolModel.tool_name).where(
                ApiKeyDisabledToolModel.api_key_id == str(api_key_id),
                ApiKeyDisabledToolModel.server_id == str(server_id),
                ApiKeyDisabledToolModel.tool_name == tool_name,
            )
            return (await session.execute(stmt)).first() is not None

    async def set_enabled(self, api_key_id: UUID, server_id: UUID, tool_name: str, enabled: bool) -> None:
        async with self._database.session() as session:
            if enabled:
                await session.execute(
                    delete(ApiKeyDisabledToolModel).where(
                        ApiKeyDisabledToolModel.api_key_id == str(api_key_id),
                        ApiKeyDisabledToolModel.server_id == str(server_id),
                        ApiKeyDisabledToolModel.tool_name == tool_name,
                    )
                )
            else:
                await session.execute(
                    insert(ApiKeyDisabledToolModel)
                    .values(api_key_id=str(api_key_id), server_id=str(server_id), tool_name=tool_name)
                    .on_conflict_do_nothing(index_elements=["api_key_id", "server_id", "tool_name"])
                )
            await session.commit()
