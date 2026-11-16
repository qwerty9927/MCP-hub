"""Session domain entities for MCP Session Explorer."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.core.enums.session_enum import SessionStatus, ToolCallStatus


@dataclass
class SessionEntity:
    """Core domain entity representing an MCP session."""

    user_id: UUID  # the owning account
    id: UUID = field(default_factory=uuid4)
    status: SessionStatus = SessionStatus.ACTIVE
    title: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_tool_calls: int = 0
    api_key_id: UUID | None = None  # API key the session's requests came with, if any
    client_fingerprint: str | None = None  # set on sessions the hub derived for sessionless clients
    # Seconds without a tool call after which the Session is completed, copied from its API key when it opened.
    # None (older rows) means DEFAULT_SESSION_IDLE_SECONDS.
    idle_timeout_seconds: int | None = None


@dataclass
class SessionDetailEntity:
    """Domain entity representing detailed session view with aggregated metrics."""

    id: UUID
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
    session_id: UUID | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None
    error_summary: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] | list[Any] | None = None
