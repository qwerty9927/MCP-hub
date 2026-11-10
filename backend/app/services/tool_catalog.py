"""Unified Tool Catalog service for aggregating and searching MCP tools."""

import asyncio
import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.core.logging import logger
from app.domain.server_entity import ServerEntity
from app.domain.tool_entity import ToolEntity
from app.infrastructure.repositories.tool_repository import ToolRepositoryAbstract
from app.schemas.common_schema import PaginatedResponse
from app.schemas.tool_schema import ToolResponse
from app.services.connection_manager import ConnectionManager


class ToolCatalogService:
    """Aggregates, caches, and indexes tools discovered across MCP servers with database persistence."""

    def __init__(self, repository: ToolRepositoryAbstract | None = None) -> None:
        self.repository = repository
        # Cache key: "{server_id}:{tool_name}"
        self._tools: dict[str, ToolEntity] = {}
        self._lock = asyncio.Lock()

    async def initialize_cache(self) -> None:
        """Pre-load discovered tools from persistent database on startup."""
        if self.repository:
            persisted = await self.repository.load_all_tools()
            async with self._lock:
                for tool in persisted:
                    self._tools[tool.id] = tool
            logger.info(f"Loaded {len(persisted)} tools from database into catalog cache")

    async def refresh_server_tools(
        self,
        server: ServerEntity,
        connection_manager: ConnectionManager,
    ) -> list[ToolEntity]:
        """Discover tools from a server, refresh database storage and update memory cache."""
        mcp_tools = await connection_manager.list_tools(server)

        discovered: list[ToolEntity] = []
        now = datetime.now(UTC)

        for mcp_tool in mcp_tools:
            qualified_id = f"{server.id}:{mcp_tool.name}"

            # Convert tool.input_schema to dict
            schema: dict[str, Any] = {}
            if hasattr(mcp_tool, "input_schema") and mcp_tool.input_schema:
                schema = (
                    mcp_tool.input_schema
                    if isinstance(mcp_tool.input_schema, dict)
                    else getattr(mcp_tool.input_schema, "model_dump", lambda: {})()
                )

            entity = ToolEntity(
                id=qualified_id,
                server_id=server.id,
                server_name=server.name,
                name=mcp_tool.name,
                description=mcp_tool.description,
                input_schema=schema,
                availability_status="AVAILABLE",
                last_discovered_at=now,
            )
            discovered.append(entity)

        # Persist to database if repository configured
        if self.repository:
            await self.repository.save_server_tools(server.id, server.name, discovered)

        async with self._lock:
            # Purge existing tools for this server ID in cache
            to_remove = [k for k, v in self._tools.items() if v.server_id == server.id]
            for k in to_remove:
                del self._tools[k]

            # Insert freshly discovered tools into cache
            for entity in discovered:
                self._tools[entity.id] = entity

        logger.info(f"Refreshed tool catalog for server '{server.name}' ({len(discovered)} tools discovered)")
        return discovered

    async def remove_server_tools(self, server_id: UUID) -> None:
        """Remove tools associated with a server when deleted or disabled."""
        if self.repository:
            await self.repository.delete_server_tools(server_id)

        async with self._lock:
            keys = [k for k, v in self._tools.items() if v.server_id == server_id]
            for k in keys:
                del self._tools[k]
        logger.info(f"Removed {len(keys)} cached tools for server {server_id}")

    async def list_tools(
        self,
        server_id: UUID | None = None,
        tool_name: str | None = None,
        status: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[ToolResponse]:
        """Search and list tools with filtering and pagination across persistent storage."""
        if self.repository:
            items, total = await self.repository.list_tools(
                server_id=server_id,
                tool_name=tool_name,
                status=status,
                search=search,
                page=page,
                page_size=page_size,
            )
        else:
            async with self._lock:
                raw_items = list(self._tools.values())

            if server_id is not None:
                raw_items = [t for t in raw_items if t.server_id == server_id]
            if tool_name:
                raw_items = [t for t in raw_items if t.name.lower() == tool_name.lower()]
            if status:
                raw_items = [t for t in raw_items if t.availability_status.lower() == status.lower()]
            if search:
                q = search.lower()
                raw_items = [
                    t
                    for t in raw_items
                    if q in t.name.lower() or (t.description and q in t.description.lower()) or q in t.server_name.lower()
                ]

            raw_items.sort(key=lambda t: (t.server_name.lower(), t.name.lower()))
            total = len(raw_items)
            start = (page - 1) * page_size
            end = start + page_size
            items = raw_items[start:end]

        read_items = [
            ToolResponse(
                id=t.id,
                name=t.name,
                description=t.description,
                input_schema=t.input_schema,
                server_id=t.server_id,
                server_name=t.server_name,
                availability_status=t.availability_status,
                last_discovered_at=t.last_discovered_at,
            )
            for t in items
        ]

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return PaginatedResponse[ToolResponse](
            items=read_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_tool(self, tool_id_or_name: str, server_id: UUID | None = None) -> ToolEntity:
        """Find a tool by qualified ID or by name and optional server_id."""
        async with self._lock:
            # 1. Exact match by qualified ID: "{server_id}:{tool_name}"
            if tool_id_or_name in self._tools:
                return self._tools[tool_id_or_name]

            # 2. Check if server_id provided
            if server_id:
                qualified = f"{server_id}:{tool_id_or_name}"
                if qualified in self._tools:
                    return self._tools[qualified]

            # 3. Match by name
            for tool in self._tools.values():
                if tool.name.lower() == tool_id_or_name.lower() and (server_id is None or tool.server_id == server_id):
                    return tool

        # If not found in cache, fallback to database repository
        if self.repository:
            db_tool = await self.repository.get_tool(tool_id_or_name, server_id=server_id)
            if db_tool:
                async with self._lock:
                    self._tools[db_tool.id] = db_tool
                return db_tool

        msg = f"Tool '{tool_id_or_name}' not found on server '{server_id}'" if server_id else f"Tool '{tool_id_or_name}' not found"
        raise NotFoundError(
            msg,
            details={
                "tool_name": tool_id_or_name,
                "server_id": str(server_id) if server_id else None,
            },
        )
