"""Tool discovery and execution endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_tool_catalog, get_tool_executor
from app.core.enums.execution_enum import ExecutionOutcomeKind, RejectionReason
from app.core.exceptions import AppError, BadGatewayError, BadRequestError, ConflictError, NotFoundError, ValidationError
from app.core.logging import get_correlation_id
from app.schemas.common_schema import PaginatedResponse
from app.schemas.tool_schema import ToolExecuteRequest, ToolExecuteResponse, ToolResponse
from app.services.tool_catalog import ToolCatalogService, qualified_tool_id
from app.services.tool_executor import ExecutionOutcome, ToolExecutor

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
    executor: Annotated[ToolExecutor, Depends(get_tool_executor)],
) -> ToolExecuteResponse:
    """Validate arguments and invoke the specified MCP tool on the target server."""
    outcome = await executor.execute(qualified_tool_id(server_id, tool_name), payload.arguments, session_id=payload.session_id)
    return _execute_response(outcome)


_REJECTION_ERRORS: dict[RejectionReason, type[AppError]] = {
    RejectionReason.UNKNOWN_TOOL: NotFoundError,
    RejectionReason.SERVER_DISABLED: BadRequestError,
    RejectionReason.TOOL_UNAVAILABLE: ConflictError,
    RejectionReason.INVALID_ARGUMENTS: ValidationError,
}


def _execute_response(outcome: ExecutionOutcome) -> ToolExecuteResponse:
    """Map an Execution Outcome to the HTTP response (or error status) of the execute route."""
    details = {"tool_reference": outcome.tool_reference, "execution_id": str(outcome.execution_id) if outcome.execution_id else None}
    if outcome.kind == ExecutionOutcomeKind.REJECTED:
        assert outcome.rejection_reason is not None
        error_cls = _REJECTION_ERRORS[outcome.rejection_reason]
        raise error_cls(outcome.error_message or "Tool execution rejected", details={**details, "reason": outcome.rejection_reason.value})
    if outcome.kind == ExecutionOutcomeKind.FAILED:
        raise BadGatewayError(outcome.error_message or "Tool execution failed", details=details)

    assert outcome.execution_id is not None and outcome.server_id is not None and outcome.tool_name is not None
    return ToolExecuteResponse(
        execution_id=outcome.execution_id,
        server_id=outcome.server_id,
        tool_name=outcome.tool_name,
        is_error=outcome.kind == ExecutionOutcomeKind.TOOL_ERROR,
        content=outcome.content,
        structured_content=outcome.structured_content,
        duration_ms=outcome.duration_ms,
        executed_at=outcome.executed_at,
        correlation_id=get_correlation_id(),
    )
