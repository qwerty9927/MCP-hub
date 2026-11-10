"""Tool discovery and execution endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_tool_catalog, get_tool_router_service
from app.schemas.common_schema import PaginatedResponse
from app.schemas.tool_schema import ToolExecuteRequest, ToolExecuteResponse, ToolResponse
from app.services.tool_catalog import ToolCatalogService
from app.services.tool_router import ToolRouterService

router = APIRouter(tags=["Tools"])


@router.get(
    "/tools",
    response_model=PaginatedResponse[ToolResponse],
    summary="List all discovered tools across MCP servers",
)
async def list_tools(
    tool_cat: Annotated[ToolCatalogService, Depends(get_tool_catalog)],
    server_id: UUID | None = Query(default=None, description="Filter by server UUID"),
    tool_name: str | None = Query(default=None, description="Filter by tool name"),
    status: str | None = Query(default=None, description="Filter by availability status"),
    search: str | None = Query(default=None, description="Search query matching name, description, or server"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginatedResponse[ToolResponse]:
    """Retrieve aggregated tool catalog with search and filtering."""
    return await tool_cat.list_tools(
        server_id=server_id,
        tool_name=tool_name,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/servers/{server_id}/tools",
    response_model=PaginatedResponse[ToolResponse],
    summary="List tools for a specific MCP server",
)
async def list_server_tools(
    server_id: UUID,
    tool_cat: Annotated[ToolCatalogService, Depends(get_tool_catalog)],
    tool_name: str | None = Query(default=None, description="Filter by tool name"),
    status: str | None = Query(default=None, description="Filter by availability status"),
    search: str | None = Query(default=None, description="Search query matching name or description"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginatedResponse[ToolResponse]:
    """Retrieve tools discovered for a specific server."""
    return await tool_cat.list_tools(
        server_id=server_id,
        tool_name=tool_name,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/tools/{tool_id:path}",
    response_model=ToolResponse,
    summary="Get tool details by ID or name",
)
async def get_tool(
    tool_id: str,
    tool_cat: Annotated[ToolCatalogService, Depends(get_tool_catalog)],
) -> ToolResponse:
    """Retrieve details and schema of a specific tool by qualified ID or name."""
    entity = await tool_cat.get_tool(tool_id)
    return ToolResponse(
        id=entity.id,
        name=entity.name,
        description=entity.description,
        input_schema=entity.input_schema,
        server_id=entity.server_id,
        server_name=entity.server_name,
        availability_status=entity.availability_status,
        last_discovered_at=entity.last_discovered_at,
    )


@router.post(
    "/servers/{server_id}/tools/{tool_name}/execute",
    response_model=ToolExecuteResponse,
    summary="Execute a tool on an MCP server",
)
async def execute_tool(
    server_id: UUID,
    tool_name: str,
    payload: ToolExecuteRequest,
    router_service: Annotated[ToolRouterService, Depends(get_tool_router_service)],
) -> ToolExecuteResponse:
    """Validate arguments and invoke the specified MCP tool on the target server."""
    kwargs = {}
    if payload.session_id is not None:
        kwargs["session_id"] = payload.session_id

    return await router_service.execute_tool(
        server_id=server_id,
        tool_name=tool_name,
        arguments=payload.arguments,
        **kwargs,
    )
