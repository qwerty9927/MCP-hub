from abc import ABC, abstractmethod
from dataclasses import replace
from uuid import UUID

from sqlalchemy import delete, exists, func, select, text, update

import app.infrastructure.database as db_module
from app.core.config import get_settings
from app.domain.tool_entity import ToolEntity
from app.helpers.validation import is_uuid
from app.models.api_key_disabled_tool_model import ApiKeyDisabledToolModel
from app.models.server_model import ServerModel
from app.models.tool_model import ToolModel


class ToolRepositoryAbstract(ABC):
    """Abstract repository for discovered tool metadata persistence."""

    @abstractmethod
    async def replace_server_tools(
        self,
        server_id: UUID,
        server_name: str,
        tools: list[ToolEntity],
        embeddings: list[list[float] | None] | None = None,
    ) -> list[ToolEntity]:
        """Replace the tools stored for a server with the newly discovered ones.

        `embeddings`, when given, holds one vector (or None) per tool, in the same order.
        """
        pass

    @abstractmethod
    async def search_by_embedding(
        self, query_embedding: list[float], *, user_id: UUID, top_k: int, api_key_id: UUID | None = None
    ) -> list[tuple[ToolEntity, float]]:
        """The owner's `top_k` searchable Tools nearest to `query_embedding`, with their cosine similarity, best first.

        Searchable: embedded, AVAILABLE, on an enabled Server, and, when `api_key_id` is given, not hidden from that key.
        """
        pass

    @abstractmethod
    async def list_tools_without_embedding(self, limit: int) -> list[ToolEntity]:
        """Up to `limit` Tools of any account that have no embedding yet (for the backfill job)."""
        pass

    @abstractmethod
    async def set_embeddings(self, embeddings: dict[UUID, list[float]]) -> None:
        """Store the embedding of each Tool, by Tool id."""
        pass

    @abstractmethod
    async def delete_server_tools(self, server_id: UUID) -> None:
        """Delete all cached tools for a specific server."""
        pass

    @abstractmethod
    async def get_tool(
        self,
        tool_id_or_name: str,
        server_id: UUID | None = None,
        *,
        user_id: UUID,
    ) -> ToolEntity | None:
        """Retrieve a tool by its id, or by name (on `server_id` only, when given)."""
        pass

    @abstractmethod
    async def list_tools(
        self,
        server_id: UUID | None = None,
        tool_name: str | None = None,
        status: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        *,
        user_id: UUID,
    ) -> tuple[list[ToolEntity], int]:
        """List and search tools across servers with pagination."""
        pass


class PostgresToolRepository(ToolRepositoryAbstract):
    """PostgreSQL implementation of ToolRepositoryAbstract using SQLAlchemy."""

    async def replace_server_tools(
        self,
        server_id: UUID,
        server_name: str,
        tools: list[ToolEntity],
        embeddings: list[list[float] | None] | None = None,
    ) -> list[ToolEntity]:
        if embeddings is not None and len(embeddings) != len(tools):
            raise ValueError(f"Got {len(embeddings)} embeddings for {len(tools)} tools")
        async with db_module.async_session_factory() as session:
            # Replace the server's tools with the newly discovered ones (each new Tool has a new id).
            await session.execute(delete(ToolModel).where(ToolModel.server_id == str(server_id)))

            saved_entities: list[ToolEntity] = []
            for index, tool in enumerate(tools):
                saved = replace(tool, server_id=server_id, server_name=server_name)
                model = ToolModel.from_domain(saved)
                model.embedding = embeddings[index] if embeddings is not None else None
                session.add(model)
                saved_entities.append(saved)

            await session.commit()
            return saved_entities

    async def search_by_embedding(
        self, query_embedding: list[float], *, user_id: UUID, top_k: int, api_key_id: UUID | None = None
    ) -> list[tuple[ToolEntity, float]]:
        async with db_module.async_session_factory() as session:
            # Filters are applied to the index's candidates; without this, a caller whose Tools are not among the
            # hnsw.ef_search (40) nearest of all accounts gets fewer than top_k, or none. Scoped to this transaction.
            await session.execute(text(f"SET LOCAL hnsw.iterative_scan = {get_settings().HNSW_ITERATIVE_SCAN}"))
            distance = ToolModel.embedding.cosine_distance(query_embedding)
            conditions = [
                ToolModel.user_id == str(user_id),
                ServerModel.enabled.is_(True),
                ToolModel.availability_status == "AVAILABLE",
                ToolModel.embedding.is_not(None),
            ]
            if api_key_id is not None:
                # ADR-0007: a tool hidden from the calling key is not searchable with it
                hidden = select(ApiKeyDisabledToolModel.tool_name).where(
                    ApiKeyDisabledToolModel.api_key_id == str(api_key_id),
                    ApiKeyDisabledToolModel.server_id == ToolModel.server_id,
                    ApiKeyDisabledToolModel.tool_name == ToolModel.name,
                )
                conditions.append(~exists(hidden))
            stmt = (
                select(ToolModel, distance.label("distance"))
                .join(ServerModel, ServerModel.id == ToolModel.server_id)
                .where(*conditions)
                .order_by(distance, ToolModel.id)
                .limit(top_k)
            )
            rows = (await session.execute(stmt)).all()
            return [(model.to_domain(), 1.0 - float(cosine_distance)) for model, cosine_distance in rows]

    async def list_tools_without_embedding(self, limit: int) -> list[ToolEntity]:
        async with db_module.async_session_factory() as session:
            stmt = select(ToolModel).where(ToolModel.embedding.is_(None)).order_by(ToolModel.id).limit(limit)
            return [model.to_domain() for model in (await session.execute(stmt)).scalars()]

    async def set_embeddings(self, embeddings: dict[UUID, list[float]]) -> None:
        if not embeddings:
            return
        async with db_module.async_session_factory() as session:
            for tool_id, vector in embeddings.items():
                await session.execute(update(ToolModel).where(ToolModel.id == str(tool_id)).values(embedding=vector))
            await session.commit()

    async def delete_server_tools(self, server_id: UUID) -> None:
        async with db_module.async_session_factory() as session:
            await session.execute(delete(ToolModel).where(ToolModel.server_id == str(server_id)))
            await session.commit()

    async def get_tool(
        self,
        tool_id_or_name: str,
        server_id: UUID | None = None,
        *,
        user_id: UUID,
    ) -> ToolEntity | None:
        async with db_module.async_session_factory() as session:
            owned = ToolModel.user_id == str(user_id)

            # 1. Look up by Tool ID
            if is_uuid(tool_id_or_name):
                stmt = select(ToolModel).where(ToolModel.id == str(UUID(tool_id_or_name)), owned)
                model = (await session.execute(stmt)).scalar_one_or_none()
                if model:
                    return model.to_domain()

            name_match = func.lower(ToolModel.name) == tool_id_or_name.lower()
            # 2. Look up by name on the given server; a named server never falls through to other servers
            if server_id is not None:
                stmt = select(ToolModel).where(ToolModel.server_id == str(server_id), name_match, owned)
                model = (await session.execute(stmt)).scalar_one_or_none()
                return model.to_domain() if model else None

            # 3. Look up by name across the owner's servers (several servers may share a tool name)
            stmt = select(ToolModel).where(name_match, owned).order_by(ToolModel.server_name.asc(), ToolModel.id.asc()).limit(1)
            model = (await session.execute(stmt)).scalars().first()
            return model.to_domain() if model else None

    async def list_tools(
        self,
        server_id: UUID | None = None,
        tool_name: str | None = None,
        status: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        *,
        user_id: UUID,
    ) -> tuple[list[ToolEntity], int]:
        async with db_module.async_session_factory() as session:
            stmt = select(ToolModel)

            stmt = stmt.where(ToolModel.user_id == str(user_id))
            if server_id is not None:
                stmt = stmt.where(ToolModel.server_id == str(server_id))
            if tool_name:
                stmt = stmt.where(func.lower(ToolModel.name) == tool_name.lower())
            if status:
                stmt = stmt.where(func.lower(ToolModel.availability_status) == status.lower())
            if search:
                term = f"%{search.lower()}%"
                stmt = stmt.where(
                    func.lower(ToolModel.name).like(term)
                    | func.lower(ToolModel.description).like(term)
                    | func.lower(ToolModel.server_name).like(term)
                )

            # Count total
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await session.execute(count_stmt)).scalar_one()

            # Sort by server_name, then name
            stmt = stmt.order_by(ToolModel.server_name.asc(), ToolModel.name.asc())

            offset = (page - 1) * page_size
            stmt = stmt.offset(offset).limit(page_size)

            result = await session.execute(stmt)
            models = result.scalars().all()
            return [model.to_domain() for model in models], total
