"""Execution Outcome enumerations (see GLOSSARY.md: Execution > Outcome)."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum


class UsageRange(StrEnum):
    """How far back tool usage metrics look."""

    DAY = "24h"
    WEEK = "7d"
    MONTH = "30d"
    ALL = "all"

    def since(self, now: datetime | None = None) -> datetime | None:
        """The earliest execution time included, or None for all time."""
        days = {UsageRange.DAY: 1, UsageRange.WEEK: 7, UsageRange.MONTH: 30}.get(self)
        return None if days is None else (now or datetime.now(UTC)) - timedelta(days=days)


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
    TOOL_DISABLED = "tool_disabled"  # hidden from the calling API key (ADR-0007)
    TOOL_UNAVAILABLE = "tool_unavailable"
    INVALID_ARGUMENTS = "invalid_arguments"
