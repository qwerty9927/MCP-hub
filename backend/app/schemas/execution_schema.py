"""Execution history schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums.execution_enum import UsageRange


class ToolUsageResponse(BaseModel):
    """How often one Tool of one Server was called in the period, and how those calls ended."""

    server_id: UUID = Field(..., description="The Server the Tool belongs to; it may since have been deleted")
    server_name: str
    tool_name: str
    total_calls: int
    completed_calls: int
    failed_calls: int
    rejected_calls: int = Field(..., description="Refused by the hub before reaching the Server (ADR-0002)")
    avg_duration_ms: float | None = Field(default=None, description="Average over calls that reached the Server")
    last_called_at: datetime


class ToolUsageReportResponse(BaseModel):
    """The most-called Tools over a period."""

    range: UsageRange
    since: datetime | None = Field(default=None, description="Start of the period; null for all time")
    total_calls: int = Field(..., description="Every call in the period, not only those of the listed Tools")
    items: list[ToolUsageResponse]


class ExecutionResponse(BaseModel):
    """Record of a tool execution."""

    id: UUID
    server_id: UUID = Field(..., description="The server that ran it; it may since have been deleted")
    server_name: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    is_error: bool
    status: str = Field(default="completed", description="Recorded status (running, completed, failed, rejected)")
    error_message: str | None = None
    duration_ms: float
    executed_at: datetime
    response: dict[str, Any] | list[Any] | None = Field(
        default=None,
        description="Response payload returned by the downstream tool execution",
    )
