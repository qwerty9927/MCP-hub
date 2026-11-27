"""Execution Outcome enumerations (see GLOSSARY.md: Execution > Outcome)."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum


class UsageRange(StrEnum):
    """How far back tool usage metrics look."""

    HOUR = "1h"
    DAY = "24h"
    WEEK = "7d"
    MONTH = "30d"
    ALL = "all"

    @property
    def span(self) -> timedelta | None:
        """Length of the period, or None for all time."""
        return _SPANS.get(self)

    @property
    def bucket(self) -> timedelta:
        """Width of one point on a calls-over-time chart for this range."""
        return _BUCKETS[self]

    def since(self, now: datetime | None = None) -> datetime | None:
        """The earliest execution time included, or None for all time."""
        span = self.span
        return None if span is None else (now or datetime.now(UTC)) - span

    def previous_period(self, now: datetime | None = None) -> tuple[datetime, datetime] | None:
        """[start, end) of the period of the same length just before this one, or None for all time."""
        span = self.span
        if span is None:
            return None
        end = (now or datetime.now(UTC)) - span
        return end - span, end


_SPANS: dict[UsageRange, timedelta] = {
    UsageRange.HOUR: timedelta(hours=1),
    UsageRange.DAY: timedelta(days=1),
    UsageRange.WEEK: timedelta(days=7),
    UsageRange.MONTH: timedelta(days=30),
}

# 12, 24, 28 and 30 points; all time is drawn by day.
_BUCKETS: dict[UsageRange, timedelta] = {
    UsageRange.HOUR: timedelta(minutes=5),
    UsageRange.DAY: timedelta(hours=1),
    UsageRange.WEEK: timedelta(hours=6),
    UsageRange.MONTH: timedelta(days=1),
    UsageRange.ALL: timedelta(days=1),
}


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
