"""Tool discovery and execution schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ToolResponse(BaseModel):
    """Discovered tool metadata schema."""

    id: str
    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    server_id: UUID
    server_name: str
    availability_status: str = "AVAILABLE"
    last_discovered_at: datetime


class ToolExecuteRequest(BaseModel):
    """Payload for executing a tool."""

    arguments: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None


class ToolContentItem(BaseModel):
    """Single item of content returned by tool execution."""

    type: str = "text"
    text: str | None = None
    data: Any | None = None


class ToolExecuteResponse(BaseModel):
    """Result returned after invoking an MCP tool."""

    execution_id: UUID
    server_id: UUID
    tool_name: str
    is_error: bool
    content: list[dict[str, Any]]
    structured_content: Any | None = None
    duration_ms: float
    executed_at: datetime
    correlation_id: str | None = None
