"""Server Registry Service."""

import math
from datetime import UTC, datetime
from uuid import UUID

from app.core.constants.oauth_constants import OAUTH_REAUTHORIZATION_REASON
from app.core.enums.server_enum import ServerAuthType, ServerHealthStatus, TransportType
from app.core.exceptions import BadGatewayError, ConflictError, NotFoundError
from app.core.logging import logger
from app.domain.server_entity import ServerEntity
from app.infrastructure.repositories.server_repository import ServerRepositoryAbstract
from app.schemas.common_schema import PaginatedResponse
from app.schemas.server_schema import (
    ServerCreateRequest,
    ServerResponse,
    ServerUpdateRequest,
)


class ServerRegistryService:
    """Manages MCP server registrations, updates, and persistence."""

    def __init__(self, server_repository: ServerRepositoryAbstract) -> None:
        self.server_repository = server_repository

    async def create_server(
        self,
        data: ServerCreateRequest,
        *,
        user_id: UUID,
        auth_type: ServerAuthType = ServerAuthType.NONE,
        oauth_provider_id: str | None = None,
    ) -> ServerResponse:
        """Register a new MCP server configuration owned by `user_id`."""
        existing = await self.server_repository.get_by_name(data.name, user_id=user_id)
        if existing:
            raise ConflictError(
                f"A server with name '{data.name}' already exists",
                details={"name": data.name},
            )

        server = ServerEntity(
            name=data.name,
            description=data.description,
            transport=data.transport,
            stdio_config=data.stdio_config,
            http_config=data.http_config,
            enabled=data.enabled,
            auth_type=auth_type,
            oauth_provider_id=oauth_provider_id,
            user_id=user_id,
            health_status=ServerHealthStatus.UNKNOWN,
        )

        saved = await self.server_repository.create(server)
        logger.info(f"Registered MCP server '{saved.name}' (id: {saved.id}, transport: {saved.transport})")
        return ServerResponse.from_domain(saved)

    async def list_server_entities(self, *, user_id: UUID) -> list[ServerEntity]:
        """Every server the account owns."""
        items, _ = await self.server_repository.list(page=1, page_size=10_000, user_id=user_id)
        return items

    async def name_is_taken(self, name: str, *, user_id: UUID) -> bool:
        """Whether the account already has a server called `name` (case-insensitive)."""
        return await self.server_repository.get_by_name(name, user_id=user_id) is not None

    async def get_server(self, server_id: UUID, *, user_id: UUID) -> ServerResponse:
        """Retrieve the owner's server by ID or raise NotFoundError."""
        entity = await self.get_server_entity(server_id, user_id=user_id)
        return ServerResponse.from_domain(entity)

    async def get_server_entity(self, server_id: UUID, *, user_id: UUID) -> ServerEntity:
        """Get the raw entity; with `user_id`, a server owned by anyone else is NotFound (no existence leak)."""
        server = await self.server_repository.get_by_id(server_id, user_id=user_id)
        if not server:
            raise NotFoundError(
                f"Server with id '{server_id}' not found",
                details={"server_id": str(server_id)},
            )
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
        *,
        user_id: UUID,
    ) -> PaginatedResponse[ServerResponse]:
        """List servers with pagination, filtering, and sorting."""
        items, total = await self.server_repository.list(
            page=page,
            page_size=page_size,
            enabled=enabled,
            transport=transport,
            health_status=health_status,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            user_id=user_id,
        )

        read_items = [ServerResponse.from_domain(server) for server in items]
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return PaginatedResponse[ServerResponse](
            items=read_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def update_server(self, server_id: UUID, data: ServerUpdateRequest, *, user_id: UUID) -> ServerResponse:
        """Update an existing server's configuration."""
        server = await self.get_server_entity(server_id, user_id=user_id)

        # Check name uniqueness if changed
        if data.name and data.name.lower() != server.name.lower():
            existing = await self.server_repository.get_by_name(data.name, user_id=server.user_id)
            if existing and existing.id != server_id:
                raise ConflictError(
                    f"A server with name '{data.name}' already exists",
                    details={"name": data.name},
                )
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
        updated = await self.server_repository.update(server)
        logger.info(f"Updated MCP server '{updated.name}' (id: {updated.id})")
        return ServerResponse.from_domain(updated)

    async def delete_server(self, server_id: UUID, *, user_id: UUID) -> bool:
        """Delete the owner's MCP server from the registry."""
        server = await self.get_server_entity(server_id, user_id=user_id)
        deleted = await self.server_repository.delete(server_id)
        if deleted:
            logger.info(f"Deleted MCP server '{server.name}' (id: {server_id})")
        return deleted

    async def record_connect_failure(
        self,
        server_id: UUID,
        exc: BaseException,
        *,
        user_id: UUID,
        fallback_status: ServerHealthStatus | None = ServerHealthStatus.UNHEALTHY,
    ) -> None:
        """Set the health a failed connect or tool sync leaves: NEEDS_AUTH when the server's OAuth tokens can no
        longer be refreshed (ADR-0008), otherwise `fallback_status` (None leaves health unchanged)."""
        if needs_reauthorization(exc):
            await self.update_health(server_id, ServerHealthStatus.NEEDS_AUTH, user_id=user_id)
        elif fallback_status is not None:
            await self.update_health(server_id, fallback_status, user_id=user_id)

    async def update_health(
        self,
        server_id: UUID,
        status: ServerHealthStatus,
        discovered_tool_count: int | None = None,
        *,
        user_id: UUID,
    ) -> None:
        """Update the owner's server health and check timestamp."""
        try:
            server = await self.get_server_entity(server_id, user_id=user_id)
            server.health_status = status
            server.last_health_check_at = datetime.now(UTC)
            if status == ServerHealthStatus.HEALTHY:
                server.last_connected_at = datetime.now(UTC)
            if discovered_tool_count is not None:
                server.discovered_tool_count = discovered_tool_count
            await self.server_repository.update(server)
        except NotFoundError:
            pass


def needs_reauthorization(exc: BaseException) -> bool:
    """Whether `exc` is the 502 raised for an OAuth server whose tokens can no longer be refreshed."""
    return isinstance(exc, BadGatewayError) and isinstance(exc.details, dict) and exc.details.get("reason") == OAUTH_REAUTHORIZATION_REASON
