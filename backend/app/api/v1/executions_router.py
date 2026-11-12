"""Execution history endpoints."""

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_execution_repository
from app.core.exceptions import NotFoundError
from app.domain.execution_entity import ExecutionEntity
from app.infrastructure.repositories.execution_repository import ExecutionRepositoryAbstract
from app.schemas.common_schema import PaginatedResponse
from app.schemas.execution_schema import ExecutionResponse

router = APIRouter(prefix="/executions", tags=["Executions"])


def _to_response(execution: ExecutionEntity) -> ExecutionResponse:
    """Map an Execution entity to its API response."""
    return ExecutionResponse(
        id=execution.id,
        server_id=execution.server_id,
        server_name=execution.server_name,
        tool_name=execution.tool_name,
        arguments=execution.arguments,
        is_error=execution.is_error,
        status=execution.status or ("failed" if execution.is_error else "completed"),
        error_message=execution.error_message,
        duration_ms=execution.duration_ms,
        executed_at=execution.executed_at,
        response=execution.response,
    )


@router.get(
    "",
    response_model=PaginatedResponse[ExecutionResponse],
    summary="List tool execution history",
)
async def list_executions(
    repo: Annotated[ExecutionRepositoryAbstract, Depends(get_execution_repository)],
    server_id: UUID | None = Query(default=None, description="Filter by server UUID"),
    tool_name: str | None = Query(default=None, description="Filter by tool name"),
    is_error: bool | None = Query(default=None, description="Filter by success/failure"),
    status: str | None = Query(default=None, description="Filter by recorded status (running, completed, failed, rejected)"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginatedResponse[ExecutionResponse]:
    """Retrieve historical log of tool execution calls with pagination and filters."""
    items, total = await repo.list(
        server_id=server_id,
        tool_name=tool_name,
        is_error=is_error,
        status=status,
        page=page,
        page_size=page_size,
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse[ExecutionResponse](
        items=[_to_response(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{execution_id}",
    response_model=ExecutionResponse,
    summary="Get execution details by ID",
)
async def get_execution(
    execution_id: UUID,
    repo: Annotated[ExecutionRepositoryAbstract, Depends(get_execution_repository)],
) -> ExecutionResponse:
    """Retrieve a specific tool execution log entry by its UUID."""
    record = await repo.get_by_id(execution_id)
    if not record:
        raise NotFoundError(
            f"Execution with id '{execution_id}' not found",
            details={"execution_id": str(execution_id)},
        )
    return _to_response(record)
