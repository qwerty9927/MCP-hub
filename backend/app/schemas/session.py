"""Pydantic schemas for MCP Session Explorer."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    """Payload for creating a new session explicitly."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] | None = None


class SessionResponse(BaseModel):
    """Session summary response schema."""

    id: str
    title: str | None = None
    status: str
    created_at: datetime
    last_activity_at: datetime
    total_tool_calls: int = 0


class SessionDetailResponse(BaseModel):
    """Detailed session view with aggregated execution metrics."""

    id: str
    title: str | None = None
    metadata: dict[str, Any] | None = None
    status: str
    created_at: datetime
    last_activity_at: datetime
    total_tool_calls: int = 0
    successful_tool_calls: int = 0
    failed_tool_calls: int = 0


class InitSessionRequest(BaseModel):
    session_id: str
    title: str | None = None
    metadata: dict[str, Any] | None = None


class ToolCallResponse(BaseModel):
    """Detailed tool execution record within a session."""

    id: UUID
    session_id: str | None = None
    server_name: str
    tool_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: float | None = None
    error_summary: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    response: Any | None = None
