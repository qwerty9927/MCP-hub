"""Session and Tool Call status enumerations."""

from enum import StrEnum


class SessionStatus(StrEnum):
    """Lifecycle status of an MCP client session."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolCallStatus(StrEnum):
    """Execution status of an individual tool call within a session."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
