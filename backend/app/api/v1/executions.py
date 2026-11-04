"""Execution history endpoints."""

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_execution_repository
from app.core.exceptions import NotFoundError
from app.infrastructure.repositories.execution_repo import ExecutionRepositoryAbstract
from app.schemas.common import PaginatedResponse
from app.schemas.execution import ExecutionRecord

router = APIRouter(prefix="/executions", tags=["Executions"])


@router.get(
    "",
    response_model=PaginatedResponse[ExecutionRecord],
    summary="List tool execution history",
)
async def list_executions(
    repo: Annotated[ExecutionRepositoryAbstract, Depends(get_execution_repository)],
    server_id: UUID | None = Query(default=None, description="Filter by server UUID"),
    tool_name: str | None = Query(default=None, description="Filter by tool name"),
    is_error: bool | None = Query(default=None, description="Filter by success/failure"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginatedResponse[ExecutionRecord]:
    """Retrieve historical log of tool execution calls with pagination and filters."""
    items, total = await repo.list(
        server_id=server_id,
        tool_name=tool_name,
        is_error=is_error,
        page=page,
        page_size=page_size,
    )

    records = [
        ExecutionRecord(
            id=e.id,
            server_id=e.server_id,
            server_name=e.server_name,
            tool_name=e.tool_name,
            arguments=e.arguments,
            is_error=e.is_error,
            error_message=e.error_message,
            duration_ms=e.duration_ms,
            executed_at=e.executed_at,
        )
        for e in items
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse[ExecutionRecord](
        items=records,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{execution_id}",
    response_model=ExecutionRecord,
    summary="Get execution details by ID",
)
async def get_execution(
    execution_id: UUID,
    repo: Annotated[ExecutionRepositoryAbstract, Depends(get_execution_repository)],
) -> ExecutionRecord:
    """Retrieve a specific tool execution log entry by its UUID."""
    record = await repo.get_by_id(execution_id)
    if not record:
        raise NotFoundError(
            f"Execution with id '{execution_id}' not found",
            details={"execution_id": str(execution_id)},
        )

    return ExecutionRecord(
        id=record.id,
        server_id=record.server_id,
        server_name=record.server_name,
        tool_name=record.tool_name,
        arguments=record.arguments,
        is_error=record.is_error,
        error_message=record.error_message,
        duration_ms=record.duration_ms,
        executed_at=record.executed_at,
    )
