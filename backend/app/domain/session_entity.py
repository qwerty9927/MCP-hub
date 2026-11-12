"""Session domain entities for MCP Session Explorer."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.enums.session_enum import SessionStatus, ToolCallStatus


@dataclass
class SessionEntity:
    """Core domain entity representing an MCP session."""

    id: str
    status: SessionStatus = SessionStatus.ACTIVE
    title: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_tool_calls: int = 0


@dataclass
class SessionDetailEntity:
    """Domain entity representing detailed session view with aggregated metrics."""

    id: str
    status: SessionStatus
    title: str | None
    metadata: dict[str, Any] | None
    created_at: datetime
    last_activity_at: datetime
    total_tool_calls: int
    successful_tool_calls: int
    failed_tool_calls: int
    rejected_tool_calls: int = 0


@dataclass
class ToolCallEntity:
    """Domain entity representing an individual tool execution within a session."""

    id: UUID
    server_name: str
    tool_name: str
    status: ToolCallStatus
    started_at: datetime
    session_id: str | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None
    error_summary: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] | list[Any] | None = None
