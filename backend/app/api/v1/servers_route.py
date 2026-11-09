"""MCP Server management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    get_connection_manager,
    get_mcp_server,
    get_server_registry_service,
    get_tool_catalog,
)
from app.core.enums.server_enum import ServerHealthStatus, TransportType
from app.schemas.common import PaginatedResponse
from app.schemas.server import (
    ServerCreate,
    ServerResponse,
    ServerTestResponse,
    ServerUpdate,
)
from app.schemas.tool import ToolResponse
from app.mcp.mcp_server import MCPServer
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
    payload: ServerCreate,
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
) -> ServerResponse:
    """Register an MCP server with stdio or streamable-http transport."""
    return await registry.create_server(payload)


@router.get(
    "",
    response_model=PaginatedResponse[ServerResponse],
    summary="List all registered MCP servers",
)
async def list_servers(
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    enabled: bool | None = Query(default=None, description="Filter by enabled status"),
    transport: TransportType | None = Query(default=None, description="Filter by transport type"),
    health_status: ServerHealthStatus | None = Query(
        default=None, description="Filter by health status"
    ),
    search: str | None = Query(
        default=None, description="Search query matching server name or description"
    ),
    sort_by: str = Query(
        default="created_at", description="Sort field (created_at, name, updated_at)"
    ),
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
    )


@router.get(
    "/{server_id}",
    response_model=ServerResponse,
    summary="Get MCP server details",
)
async def get_server(
    server_id: UUID,
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
) -> ServerResponse:
    """Get complete configuration and status of an MCP server by ID."""
    return await registry.get_server(server_id)


@router.patch(
    "/{server_id}",
    response_model=ServerResponse,
    summary="Update MCP server configuration",
)
async def update_server(
    server_id: UUID,
    payload: ServerUpdate,
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
    mcp_server: Annotated[MCPServer, Depends(get_mcp_server)],
) -> ServerResponse:
    """Update configuration attributes of an existing MCP server."""
    result = await registry.update_server(server_id, payload)
    await mcp_server.notify_tools_changed()
    return result


@router.delete(
    "/{server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an MCP server",
)
async def delete_server(
    server_id: UUID,
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
    connection_mgr: Annotated[ConnectionManager, Depends(get_connection_manager)],
    tool_cat: Annotated[ToolCatalogService, Depends(get_tool_catalog)],
    mcp_server: Annotated[MCPServer, Depends(get_mcp_server)],
) -> None:
    """Remove server registration, close active connections, and purge cached tools."""
    await connection_mgr.disconnect(server_id)
    await tool_cat.remove_server_tools(server_id)
    await registry.delete_server(server_id)
    await mcp_server.notify_tools_changed()


@router.post(
    "/{server_id}/connect",
    response_model=ServerResponse,
    summary="Connect to MCP server",
)
async def connect_server(
    server_id: UUID,
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
    connection_mgr: Annotated[ConnectionManager, Depends(get_connection_manager)],
    tool_cat: Annotated[ToolCatalogService, Depends(get_tool_catalog)],
    mcp_server: Annotated[MCPServer, Depends(get_mcp_server)],
) -> ServerResponse:
    """Establish active session to the server and discover available tools."""
    server = await registry.get_server_entity(server_id)
    try:
        await connection_mgr.get_or_create_session(server)
        tools = await tool_cat.refresh_server_tools(server, connection_mgr)
        await registry.update_health(server_id, ServerHealthStatus.HEALTHY, len(tools))
        await mcp_server.notify_tools_changed()
    except Exception:
        await registry.update_health(server_id, ServerHealthStatus.UNHEALTHY)
        raise

    return await registry.get_server(server_id)


@router.post(
    "/{server_id}/disconnect",
    response_model=ServerResponse,
    summary="Disconnect from MCP server",
)
async def disconnect_server(
    server_id: UUID,
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
    connection_mgr: Annotated[ConnectionManager, Depends(get_connection_manager)],
    mcp_server: Annotated[MCPServer, Depends(get_mcp_server)],
) -> ServerResponse:
    """Disconnect active session for the given server."""
    await registry.get_server_entity(server_id)
    await connection_mgr.disconnect(server_id)
    await registry.update_health(server_id, ServerHealthStatus.DISCONNECTED)
    await mcp_server.notify_tools_changed()
    return await registry.get_server(server_id)


@router.post(
    "/{server_id}/test-connection",
    response_model=ServerTestResponse,
    summary="Test connectivity to MCP server",
)
async def test_server_connection(
    server_id: UUID,
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
    connection_mgr: Annotated[ConnectionManager, Depends(get_connection_manager)],
) -> ServerTestResponse:
    """Perform a ping and tool listing check without persisting permanent session."""
    server = await registry.get_server_entity(server_id)
    success, message, count, latency = await connection_mgr.test_connection(server)
    new_status = ServerHealthStatus.HEALTHY if success else ServerHealthStatus.UNHEALTHY
    await registry.update_health(server_id, new_status, count if success else None)

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
    registry: Annotated[ServerRegistryService, Depends(get_server_registry_service)],
    connection_mgr: Annotated[ConnectionManager, Depends(get_connection_manager)],
    tool_cat: Annotated[ToolCatalogService, Depends(get_tool_catalog)],
    mcp_server: Annotated[MCPServer, Depends(get_mcp_server)],
) -> list[ToolResponse]:
    """Query the MCP server for tools and update the unified catalog cache."""
    server = await registry.get_server_entity(server_id)
    tools = await tool_cat.refresh_server_tools(server, connection_mgr)
    await registry.update_health(server_id, ServerHealthStatus.HEALTHY, len(tools))
    await mcp_server.notify_tools_changed()

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
