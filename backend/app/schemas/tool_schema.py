"""Tool discovery and execution schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ToolResponse(BaseModel):
    """Discovered tool metadata schema."""

    id: str = Field(..., description="Unique server-qualified identifier: '{server_id}:{tool_name}'")
    name: str = Field(..., description="Tool name exposed by the MCP server")
    description: str | None = Field(default=None, description="Tool description provided by server")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="JSON schema defining input arguments")
    server_id: UUID = Field(..., description="UUID of the parent MCP server")
    server_name: str = Field(..., description="Name of the parent MCP server")
    availability_status: str = Field(default="AVAILABLE", description="Tool availability (AVAILABLE, UNAVAILABLE)")
    last_discovered_at: datetime = Field(..., description="Timestamp of when tool was last discovered/refreshed")


# Backward-compatible alias
ToolRead = ToolResponse


class ToolSummaryResponse(BaseModel):
    """Compact summary of a discovered tool."""

    id: str = Field(..., description="Unique server-qualified identifier: '{server_id}:{tool_name}'")
    name: str = Field(..., description="Tool name")
    server_id: UUID = Field(..., description="Parent server UUID")
    server_name: str = Field(..., description="Parent server name")
    description: str | None = None
    availability_status: str = "AVAILABLE"


# Backward-compatible alias
ToolSummaryRead = ToolSummaryResponse


class ToolExecuteRequest(BaseModel):
    """Payload for executing a tool."""

    arguments: dict[str, Any] = Field(default_factory=dict, description="Key-value arguments matching tool inputSchema")
    session_id: str | None = Field(default=None, description="Optional session ID to associate with this tool execution")


class ToolContentItem(BaseModel):
    """Single item of content returned by tool execution."""

    type: str = Field(default="text", description="Type of content: text, image, resource, etc.")
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
    correlation_id: str | None = Field(default=None, description="Request correlation ID for execution tracing")
