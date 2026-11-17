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
