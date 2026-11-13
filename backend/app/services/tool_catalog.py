"""Unified Tool Catalog service for aggregating and searching MCP tools."""

import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.core.logging import logger
from app.domain.server_entity import ServerEntity
from app.domain.tool_entity import ToolEntity
from app.helpers.text import slugify
from app.infrastructure.repositories.tool_repository import ToolRepositoryAbstract
from app.schemas.common_schema import PaginatedResponse
from app.schemas.tool_schema import ToolResponse
from app.services.connection_manager import ConnectionManager


def qualified_tool_id(server_id: UUID, tool_name: str) -> str:
    """Build a Qualified Tool ID "{server_id}:{tool_name}"."""
    return f"{server_id}:{tool_name}"


def split_qualified_tool_id(tool_reference: str) -> tuple[UUID | None, str]:
    """Split a Qualified Tool ID "{server_id}:{tool_name}"; returns (None, reference) for anything else."""
    prefix, sep, tool_name = tool_reference.partition(":")
    if not sep or not tool_name:
        return None, tool_reference
    try:
        return UUID(prefix), tool_name
    except ValueError:
        return None, tool_reference


class ToolCatalogService:
    """Indexes the tools discovered across MCP servers. Every read goes to the database; nothing is cached in memory."""

    def __init__(self, repository: ToolRepositoryAbstract) -> None:
        self.repository = repository

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
                    id=qualified_tool_id(server.id, mcp_tool.name),
                    server_id=server.id,
                    server_name=server.name,
                    owner_id=server.owner_id,
                    name=mcp_tool.name,
                    description=mcp_tool.description,
                    input_schema=schema,
                    availability_status="AVAILABLE",
                    last_discovered_at=now,
                )
            )

        await self.repository.save_server_tools(server.id, server.name, discovered)
        logger.info(f"Refreshed tool catalog for server '{server.name}' ({len(discovered)} tools discovered)")
        return discovered

    async def remove_server_tools(self, server_id: UUID) -> None:
        """Remove tools associated with a server when deleted or disabled."""
        await self.repository.delete_server_tools(server_id)
        logger.info(f"Removed stored tools for server {server_id}")

    async def list_tools(
        self,
        server_id: UUID | None = None,
        tool_name: str | None = None,
        status: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        owner_id: UUID | None = None,
    ) -> PaginatedResponse[ToolResponse]:
        """Search and list tools with filtering and pagination; `owner_id` limits it to that account's Servers."""
        items, total = await self.repository.list_tools(
            server_id=server_id,
            tool_name=tool_name,
            status=status,
            search=search,
            page=page,
            page_size=page_size,
            owner_id=owner_id,
        )

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

    async def resolve(self, tool_reference: str, *, owner_id: UUID | None) -> ToolEntity | None:
        """Resolve a Tool Reference (Qualified Tool ID or Tool Slug) to one of the owner's Tools, or None."""
        server_id, tool_name = split_qualified_tool_id(tool_reference)
        if server_id is not None:
            try:
                return await self.get_tool(tool_name, server_id=server_id, owner_id=owner_id)
            except NotFoundError:
                return None

        try:
            return await self.get_tool(tool_reference, owner_id=owner_id)
        except NotFoundError:
            pass

        # Tool Slug: "{server_slug}__{tool_name}" (unique per owner, since server names are)
        if "__" not in tool_reference:
            return None
        server_slug, slug_tool_name = tool_reference.split("__", 1)
        candidates = await self.list_tools(tool_name=slug_tool_name, page=1, page_size=100, owner_id=owner_id)
        for candidate in candidates.items:
            if slugify(candidate.server_name) == server_slug:
                return await self.get_tool(candidate.id, owner_id=owner_id)
        return None

    async def get_tool(self, tool_id_or_name: str, server_id: UUID | None = None, owner_id: UUID | None = None) -> ToolEntity:
        """Find a tool by qualified ID, or by name on `server_id` (only that server) or on any of the owner's servers."""
        tool = await self.repository.get_tool(tool_id_or_name, server_id=server_id, owner_id=owner_id)
        if tool is not None:
            return tool

        msg = f"Tool '{tool_id_or_name}' not found on server '{server_id}'" if server_id else f"Tool '{tool_id_or_name}' not found"
        raise NotFoundError(
            msg,
            details={
                "tool_name": tool_id_or_name,
                "server_id": str(server_id) if server_id else None,
            },
        )
