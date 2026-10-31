"""Execution history schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionRecord(BaseModel):
    """Record of a tool execution."""

    id: UUID
    server_id: UUID
    server_name: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    is_error: bool
    error_message: str | None = None
    duration_ms: float
    executed_at: datetime
