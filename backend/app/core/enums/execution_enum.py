"""Execution Outcome enumerations (see GLOSSARY.md: Execution > Outcome)."""

from enum import StrEnum


class ExecutionOutcomeKind(StrEnum):
    """How an attempt to execute a Tool ended."""

    SUCCEEDED = "succeeded"
    TOOL_ERROR = "tool_error"
    FAILED = "failed"
    REJECTED = "rejected"


class RejectionReason(StrEnum):
    """Why the hub refused an attempt before contacting the downstream Server."""

    UNKNOWN_TOOL = "unknown_tool"
    SERVER_DISABLED = "server_disabled"
    TOOL_UNAVAILABLE = "tool_unavailable"
    INVALID_ARGUMENTS = "invalid_arguments"
