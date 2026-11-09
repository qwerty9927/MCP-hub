"""Pydantic schemas for MCP Session Explorer."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    """Payload for creating a new session explicitly."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None, max_length=255, description="Human-readable title or label"
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Optional metadata or client attributes"
    )


class SessionResponse(BaseModel):
    """Session summary response schema."""

    id: str = Field(..., description="Unique session identifier")
    title: str | None = Field(default=None, description="Session title or identifier")
    status: str = Field(..., description="Session lifecycle status (active, completed, failed)")
    created_at: datetime = Field(..., description="Timestamp when session was created")
    last_activity_at: datetime = Field(
        ..., description="Timestamp of most recent activity in session"
    )
    total_tool_calls: int = Field(
        default=0, description="Total count of tool calls belonging to this session"
    )


class SessionDetailResponse(BaseModel):
    """Detailed session view with aggregated execution metrics."""

    id: str = Field(..., description="Unique session identifier")
    title: str | None = Field(default=None, description="Session title or identifier")
    metadata: dict[str, Any] | None = Field(
        default=None, description="Session metadata or client properties"
    )
    status: str = Field(..., description="Session lifecycle status (active, completed, failed)")
    created_at: datetime = Field(..., description="Timestamp when session was created")
    last_activity_at: datetime = Field(
        ..., description="Timestamp of most recent activity in session"
    )
    total_tool_calls: int = Field(default=0, description="Total count of tool calls in session")
    successful_tool_calls: int = Field(
        default=0, description="Total number of successfully executed tool calls"
    )
    failed_tool_calls: int = Field(default=0, description="Total number of failed tool calls")


class ToolCallResponse(BaseModel):
    """Detailed tool execution record within a session."""

    id: UUID = Field(..., description="Unique call ID")
    session_id: str | None = Field(default=None, description="Parent session ID")
    server_name: str = Field(..., description="Name of the MCP server")
    tool_name: str = Field(..., description="Name of the executed tool")
    status: str = Field(..., description="Execution status (running, completed, failed)")
    started_at: datetime = Field(..., description="Timestamp when tool execution started")
    completed_at: datetime | None = Field(
        default=None, description="Timestamp when tool execution finished"
    )
    duration_ms: float | None = Field(
        default=None, description="Execution duration in milliseconds"
    )
    error_summary: str | None = Field(
        default=None, description="Summary error message if execution failed"
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Tool execution input arguments"
    )
    response: Any | None = Field(default=None, description="Output payload returned by the tool")
