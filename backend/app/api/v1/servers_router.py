"""MCP Server management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    get_connection_manager,
    get_current_principal,
    get_server_registry_service,
    get_tool_catalog_service,
)
from app.core.enums.server_enum import ServerHealthStatus, TransportType
from app.domain.principal_entity import Principal
from app.schemas.common_schema import PaginatedResponse
from app.schemas.server_schema import (
    ServerCreateRequest,
    ServerResponse,
    ServerTestResponse,
    ServerUpdateRequest,
)
from app.schemas.tool_schema import ToolResponse
from app.services.connection_manager import ConnectionManager
from app.services.server_registry import ServerRegistryService
from app.services.tool_catalog import ToolCatalogService

router = APIRouter(prefix="/servers", tags=["Servers"])


@router.post(
    "",
    response_model=ServerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new MCP server",
)
async def create_server(
    payload: ServerCreateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    server_registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
) -> ServerResponse:
    """Register an MCP server with stdio or streamable-http transport."""
    return await server_registry.create_server(payload, user_id=principal.user_id)


@router.get(
    "",
    response_model=PaginatedResponse[ServerResponse],
    summary="List all registered MCP servers",
)
async def list_servers(
    principal: Annotated[Principal, Depends(get_current_principal)],
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    enabled: bool | None = Query(default=None, description="Filter by enabled status"),
    transport: TransportType | None = Query(default=None, description="Filter by transport type"),
    health_status: ServerHealthStatus | None = Query(default=None, description="Filter by health status"),
    search: str | None = Query(default=None, description="Search query matching server name or description"),
    sort_by: str = Query(default="created_at", description="Sort field (created_at, name, updated_at)"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort order"),
) -> PaginatedResponse[ServerResponse]:
    """Retrieve paginated MCP servers with optional filtering and sorting."""
    return await registry.list_servers(
        page=page,
        page_size=page_size,
        enabled=enabled,
        transport=transport,
        health_status=health_status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        user_id=principal.user_id,
    )


@router.get(
    "/{server_id}",
    response_model=ServerResponse,
    summary="Get MCP server details",
)
async def get_server(
    server_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
) -> ServerResponse:
    """Get complete configuration and status of an MCP server by ID."""
    return await registry.get_server(server_id, user_id=principal.user_id)


@router.patch(
    "/{server_id}",
    response_model=ServerResponse,
    summary="Update MCP server configuration",
)
async def update_server(
    server_id: UUID,
    payload: ServerUpdateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
) -> ServerResponse:
    """Update configuration attributes of an existing MCP server."""
    result = await registry.update_server(server_id, payload, user_id=principal.user_id)
    return result


@router.delete(
    "/{server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an MCP server",
)
async def delete_server(
    server_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
    connection_mgr: Annotated[ConnectionManager, Depends(get_connection_manager)],
    tool_cat: Annotated[ToolCatalogService, Depends(get_tool_catalog_service)],
) -> None:
    """Remove server registration, close active connections, and delete its stored tools."""
    await registry.get_server_entity(server_id, user_id=principal.user_id)
    await connection_mgr.disconnect(server_id)
    await tool_cat.remove_server_tools(server_id)
    await registry.delete_server(server_id, user_id=principal.user_id)


@router.post(
    "/{server_id}/connect",
    response_model=ServerResponse,
    summary="Connect to MCP server",
)
async def connect_server(
    server_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
    connection_mgr: Annotated[ConnectionManager, Depends(get_connection_manager)],
    tool_cat: Annotated[ToolCatalogService, Depends(get_tool_catalog_service)],
) -> ServerResponse:
    """Establish active session to the server and discover available tools."""
    server = await registry.get_server_entity(server_id, user_id=principal.user_id)
    try:
        await connection_mgr.get_or_create_session(server)
        tools = await tool_cat.refresh_server_tools(server, connection_mgr)
        await registry.update_health(server_id, ServerHealthStatus.HEALTHY, len(tools), user_id=principal.user_id)
    except Exception:
        await registry.update_health(server_id, ServerHealthStatus.UNHEALTHY, user_id=principal.user_id)
        raise

    return await registry.get_server(server_id, user_id=principal.user_id)


@router.post(
    "/{server_id}/disconnect",
    response_model=ServerResponse,
    summary="Disconnect from MCP server",
)
async def disconnect_server(
    server_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
    connection_mgr: Annotated[ConnectionManager, Depends(get_connection_manager)],
) -> ServerResponse:
    """Disconnect active session for the given server."""
    await registry.get_server_entity(server_id, user_id=principal.user_id)
    await connection_mgr.disconnect(server_id)
    await registry.update_health(server_id, ServerHealthStatus.DISCONNECTED, user_id=principal.user_id)
    return await registry.get_server(server_id, user_id=principal.user_id)


@router.post(
    "/{server_id}/test-connection",
    response_model=ServerTestResponse,
    summary="Test connectivity to MCP server",
)
async def test_server_connection(
    server_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
    connection_mgr: Annotated[ConnectionManager, Depends(get_connection_manager)],
) -> ServerTestResponse:
    """Perform a ping and tool listing check without persisting permanent session."""
    server = await registry.get_server_entity(server_id, user_id=principal.user_id)
    success, message, count, latency = await connection_mgr.test_connection(server)
    new_status = ServerHealthStatus.HEALTHY if success else ServerHealthStatus.UNHEALTHY
    await registry.update_health(server_id, new_status, count if success else None, user_id=principal.user_id)

    return ServerTestResponse(
        success=success,
        message=message,
        tools_count=count,
        latency_ms=latency,
    )


@router.post(
    "/{server_id}/refresh-tools",
    response_model=list[ToolResponse],
    summary="Refresh tools catalog for server",
)
async def refresh_server_tools(
    server_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    server_registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
    connection_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    tool_catalog: Annotated[ToolCatalogService, Depends(get_tool_catalog_service)],
) -> list[ToolResponse]:
    """Query the MCP server for tools and replace its entries in the tool catalog."""
    server = await server_registry.get_server_entity(server_id, user_id=principal.user_id)
    tools = await tool_catalog.refresh_server_tools(server, connection_manager)
    await server_registry.update_health(server_id, ServerHealthStatus.HEALTHY, len(tools), user_id=principal.user_id)

    return [
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
        for t in tools
    ]
