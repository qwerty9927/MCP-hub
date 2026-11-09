"""MCP Session Explorer endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_session_explorer_service
from app.schemas.common import PaginatedResponse
from app.schemas.session import (
    SessionCreate,
    SessionDetailResponse,
    SessionResponse,
    ToolCallResponse,
)
from app.services.session_explorer import SessionExplorerService

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new MCP session",
)
async def create_session(
    payload: SessionCreate,
    service: Annotated[SessionExplorerService, Depends(get_session_explorer_service)],
) -> SessionResponse:
    """Explicitly create a new session."""
    return await service.create_session(payload)


@router.get(
    "",
    response_model=PaginatedResponse[SessionResponse],
    summary="List MCP client sessions",
)
async def list_sessions(
    service: Annotated[SessionExplorerService, Depends(get_session_explorer_service)],
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(default=None, description="Search term matching session ID or title"),
    status: str | None = Query(default=None, description="Filter by session status (active, completed, failed)"),
) -> PaginatedResponse[SessionResponse]:
    """Retrieve existing MCP sessions with database-side pagination and filters."""
    return await service.list_sessions(
        page=page,
        page_size=page_size,
        search=search,
        status=status,
    )


@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    summary="Get session details and execution metrics",
)
async def get_session(
    session_id: str,
    service: Annotated[SessionExplorerService, Depends(get_session_explorer_service)],
) -> SessionDetailResponse:
    """Retrieve session details with aggregated tool execution counts."""
    return await service.get_session(session_id)


@router.get(
    "/{session_id}/tool-calls",
    response_model=PaginatedResponse[ToolCallResponse],
    summary="List tool execution history for a session",
)
async def list_session_tool_calls(
    session_id: str,
    service: Annotated[SessionExplorerService, Depends(get_session_explorer_service)],
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query(
        default="created_at",
        description="Sort field (created_at, started_at, completed_at, duration_ms, server_name, tool_name, status)",
    ),
    order: str = Query(default="asc", pattern="^(asc|desc)$", description="Sort order (asc, desc)"),
    status: str | None = Query(default=None, description="Filter by tool call status (running, completed, failed)"),
    server_name: str | None = Query(default=None, description="Filter by server name"),
    tool_name: str | None = Query(default=None, description="Filter by tool name"),
) -> PaginatedResponse[ToolCallResponse]:
    """Retrieve all tool calls belonging to a session in chronological order with pagination and filters."""
    return await service.list_session_tool_calls(
        session_id=session_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        order=order,
        status=status,
        server_name=server_name,
        tool_name=tool_name,
    )


@router.get(
    "/{session_id}/tool-calls/{call_id}",
    response_model=ToolCallResponse,
    summary="Get specific tool call details within a session",
)
async def get_session_tool_call(
    session_id: str,
    call_id: UUID,
    service: Annotated[SessionExplorerService, Depends(get_session_explorer_service)],
) -> ToolCallResponse:
    """Retrieve an individual tool call by its UUID within a session."""
    return await service.get_session_tool_call(session_id, call_id)
