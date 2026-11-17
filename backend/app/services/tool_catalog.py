"""Unified Tool Catalog service for aggregating and searching MCP tools."""

import asyncio
import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.core.exceptions import NotFoundError
from app.core.logging import logger
from app.domain.server_entity import ServerEntity
from app.domain.tool_entity import ToolEntity
from app.helpers.text import slugify
from app.infrastructure.repositories.tool_repository import ToolRepositoryAbstract
from app.schemas.common_schema import PaginatedResponse
from app.schemas.tool_schema import ToolResponse
from app.services.connection_manager import ConnectionManager
from app.services.embedding_service import EmbeddingServiceAbstract, tool_embedding_text


class ToolCatalogService:
    """Indexes the tools discovered across MCP servers. Every read goes to the database; nothing is cached in memory."""

    def __init__(self, tool_repository: ToolRepositoryAbstract, embedding_service: EmbeddingServiceAbstract) -> None:
        self._tool_repository = tool_repository
        self._embedding_service = embedding_service

    async def refresh_server_tools(
        self,
        server: ServerEntity,
        connection_manager: ConnectionManager,
    ) -> list[ToolEntity]:
        """Discover tools from a server and replace its stored tools with them."""
        mcp_tools = await connection_manager.list_tools(server)

        discovered: list[ToolEntity] = []
        now = datetime.now(UTC)

        for mcp_tool in mcp_tools:
            # Convert tool.input_schema to dict
            schema: dict[str, Any] = {}
            if hasattr(mcp_tool, "input_schema") and mcp_tool.input_schema:
                schema = (
                    mcp_tool.input_schema
                    if isinstance(mcp_tool.input_schema, dict)
                    else getattr(mcp_tool.input_schema, "model_dump", lambda: {})()
                )

            discovered.append(
                ToolEntity(
                    id=uuid4(),
                    server_id=server.id,
                    server_name=server.name,
                    user_id=server.user_id,
                    name=mcp_tool.name,
                    description=mcp_tool.description,
                    input_schema=schema,
                    availability_status="AVAILABLE",
                    last_discovered_at=now,
                )
            )

        embeddings = await self._embed_tools(discovered)
        saved = await self._tool_repository.replace_server_tools(server.id, server.name, discovered, embeddings)
        logger.info(f"Refreshed tool catalog for server '{server.name}' ({len(saved)} tools discovered)")
        return saved

    async def search(
        self, queries: list[str], *, user_id: UUID, top_k: int, api_key_id: UUID | None = None
    ) -> list[list[tuple[ToolEntity, float]]]:
        """For each query, the owner's `top_k` searchable Tools by cosine similarity, best first (ADR-0006).

        With `api_key_id`, Tools hidden from that key are left out (ADR-0007).
        """
        vectors = await asyncio.gather(*(self._embedding_service.embed_query(query) for query in queries))
        return [
            await self._tool_repository.search_by_embedding(vector, user_id=user_id, top_k=top_k, api_key_id=api_key_id)
            for vector in vectors
        ]

    async def remove_server_tools(self, server_id: UUID) -> None:
        """Remove tools associated with a server when deleted or disabled."""
        await self._tool_repository.delete_server_tools(server_id)
        logger.info(f"Removed stored tools for server {server_id}")

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
    ) -> PaginatedResponse[ToolResponse]:
        """Search and list tools with filtering and pagination; `user_id` limits it to that account's Servers."""
        items, total = await self._tool_repository.list_tools(
            server_id=server_id,
            tool_name=tool_name,
            status=status,
            search=search,
            page=page,
            page_size=page_size,
            user_id=user_id,
        )

        read_items = [
            ToolResponse(
                id=tool.id,
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
                server_id=tool.server_id,
                server_name=tool.server_name,
                availability_status=tool.availability_status,
                last_discovered_at=tool.last_discovered_at,
            )
            for tool in items
        ]

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return PaginatedResponse[ToolResponse](
            items=read_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def resolve(self, tool_reference: str, *, user_id: UUID, server_id: UUID | None = None) -> ToolEntity | None:
        """Resolve a Tool Reference to one of the owner's Tools, or None.

        With `server_id`, the reference is a tool name on that Server only. Without it, it is a Tool ID, a tool name
        or a Tool Slug.
        """
        if server_id is not None:
            try:
                return await self.get_tool(tool_reference, server_id=server_id, user_id=user_id)
            except NotFoundError:
                return None

        try:
            return await self.get_tool(tool_reference, user_id=user_id)
        except NotFoundError:
            pass

        # Tool Slug: "{server_slug}__{tool_name}" (unique per owner, since server names are)
        if "__" not in tool_reference:
            return None
        server_slug, slug_tool_name = tool_reference.split("__", 1)
        candidates = await self.list_tools(tool_name=slug_tool_name, page=1, page_size=100, user_id=user_id)
        for candidate in candidates.items:
            if slugify(candidate.server_name) == server_slug:
                return await self.get_tool(str(candidate.id), user_id=user_id)
        return None

    async def get_tool(self, tool_id_or_name: str, server_id: UUID | None = None, *, user_id: UUID) -> ToolEntity:
        """Find a tool by its id, or by name on `server_id` (only that server) or on any of the owner's servers."""
        tool = await self._tool_repository.get_tool(tool_id_or_name, server_id=server_id, user_id=user_id)
        if tool is not None:
            return tool

        message = f"Tool '{tool_id_or_name}' not found on server '{server_id}'" if server_id else f"Tool '{tool_id_or_name}' not found"
        raise NotFoundError(
            message,
            details={
                "tool_name": tool_id_or_name,
                "server_id": str(server_id) if server_id else None,
            },
        )

    async def _embed_tools(self, tools: list[ToolEntity]) -> list[list[float] | None]:
        """One embedding per Tool; all None when embedding fails, so discovery never fails because of search."""
        try:
            return list(await self._embedding_service.embed_documents([tool_embedding_text(tool) for tool in tools]))
        except Exception as exc:
            logger.warning(f"Could not embed {len(tools)} tools; they are not searchable until the backfill embeds them: {exc}")
            return [None] * len(tools)
