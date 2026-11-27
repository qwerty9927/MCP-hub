"""Execution domain entity."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class ExecutionEntity:
    """Core domain entity representing a tool execution record."""

    id: UUID
    server_id: UUID  # kept after the Server is deleted
    user_id: UUID  # the owner; history is scoped by it, so it survives deleting the Server
    server_name: str
    tool_name: str
    arguments: dict[str, Any]
    is_error: bool
    duration_ms: float
    executed_at: datetime
    error_message: str | None = None
    response: dict[str, Any] | list[Any] | None = None
    session_id: UUID | None = None
    status: str = "completed"
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class ToolUsageEntity:
    """How often one Tool of one Server was called over a period, and how those calls ended."""

    server_id: UUID
    server_name: str
    tool_name: str
    total_calls: int
    completed_calls: int
    failed_calls: int
    rejected_calls: int
    avg_duration_ms: float | None  # over calls that reached the Server; rejected ones never did
    last_called_at: datetime
    p90_duration_ms: float | None = None  # 90th percentile, over the same calls as the average


@dataclass
class CallStatsEntity:
    """Totals over every call in a period (optionally one Server's)."""

    total_calls: int
    completed_calls: int
    failed_calls: int
    rejected_calls: int
    p90_duration_ms: float | None  # over calls that reached the Server


@dataclass
class CallBucketEntity:
    """Calls that started in one time bucket [start, start + bucket)."""

    start: datetime
    total_calls: int
    completed_calls: int
    failed_calls: int
    rejected_calls: int
