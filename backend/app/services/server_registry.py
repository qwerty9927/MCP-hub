"""Server Registry Service."""

import math
from datetime import UTC, datetime
from uuid import UUID

from app.core.exceptions import ServerAlreadyExistsError, ServerNotFoundError
from app.core.logging import logger
from app.domain.entities import ServerEntity
from app.infrastructure.repositories.base import ServerRepositoryBase
from app.schemas.common import PaginatedResponse
from app.schemas.server import (
    ServerCreate,
    ServerHealthStatus,
    ServerRead,
    ServerUpdate,
    TransportType,
)


class ServerRegistryService:
    """Manages MCP server registrations, updates, and persistence."""

    def __init__(self, repository: ServerRepositoryBase) -> None:
        self.repository = repository

    async def create_server(self, data: ServerCreate) -> ServerRead:
        """Register a new MCP server configuration."""
        existing = await self.repository.get_by_name(data.name)
        if existing:
            raise ServerAlreadyExistsError(data.name)

        server = ServerEntity(
            name=data.name,
            description=data.description,
            transport=data.transport,
            stdio_config=data.stdio_config,
            http_config=data.http_config,
            enabled=data.enabled,
            health_status=ServerHealthStatus.UNKNOWN,
        )

        saved = await self.repository.create(server)
        logger.info(
            f"Registered MCP server '{saved.name}' (id: {saved.id}, transport: {saved.transport})"
        )
        return ServerRead.from_domain(saved)

    async def get_server(self, server_id: UUID) -> ServerRead:
        """Retrieve server by ID or raise ServerNotFoundError."""
        entity = await self.get_server_entity(server_id)
        return ServerRead.from_domain(entity)

    async def get_server_entity(self, server_id: UUID) -> ServerEntity:
        """Internal helper to get raw domain entity."""
        server = await self.repository.get_by_id(server_id)
        if not server:
            raise ServerNotFoundError(str(server_id))
        return server

    async def list_servers(
        self,
        page: int = 1,
        page_size: int = 20,
        enabled: bool | None = None,
        transport: TransportType | None = None,
        health_status: ServerHealthStatus | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedResponse[ServerRead]:
        """List servers with pagination, filtering, and sorting."""
        items, total = await self.repository.list(
            page=page,
            page_size=page_size,
            enabled=enabled,
            transport=transport,
            health_status=health_status,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        read_items = [ServerRead.from_domain(s) for s in items]
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return PaginatedResponse[ServerRead](
            items=read_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def update_server(self, server_id: UUID, data: ServerUpdate) -> ServerRead:
        """Update an existing server's configuration."""
        server = await self.get_server_entity(server_id)

        # Check name uniqueness if changed
        if data.name and data.name.lower() != server.name.lower():
            existing = await self.repository.get_by_name(data.name)
            if existing and existing.id != server_id:
                raise ServerAlreadyExistsError(data.name)
            server.name = data.name

        if data.description is not None:
            server.description = data.description
        if data.transport is not None:
            server.transport = data.transport
        if data.stdio_config is not None:
            server.stdio_config = data.stdio_config
        if data.http_config is not None:
            server.http_config = data.http_config
        if data.enabled is not None:
            server.enabled = data.enabled

        server.updated_at = datetime.now(UTC)
        updated = await self.repository.update(server)
        logger.info(f"Updated MCP server '{updated.name}' (id: {updated.id})")
        return ServerRead.from_domain(updated)

    async def delete_server(self, server_id: UUID) -> bool:
        """Delete an MCP server from the registry."""
        server = await self.get_server_entity(server_id)
        deleted = await self.repository.delete(server_id)
        if deleted:
            logger.info(f"Deleted MCP server '{server.name}' (id: {server_id})")
        return deleted

    async def update_health(
        self,
        server_id: UUID,
        status: ServerHealthStatus,
        discovered_tool_count: int | None = None,
    ) -> None:
        """Update server health and check timestamp."""
        try:
            server = await self.get_server_entity(server_id)
            server.health_status = status
            server.last_health_check_at = datetime.now(UTC)
            if status == ServerHealthStatus.HEALTHY:
                server.last_connected_at = datetime.now(UTC)
            if discovered_tool_count is not None:
                server.discovered_tool_count = discovered_tool_count
            await self.repository.update(server)
        except ServerNotFoundError:
            pass
