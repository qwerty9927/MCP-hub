"""Session idle-timeout helpers shared by the Session tracker and the background job that completes idle Sessions."""

from datetime import datetime, timedelta

from app.core.constants.session_constants import DEFAULT_SESSION_IDLE_SECONDS


def idle_minutes_to_seconds(minutes: int | None) -> int | None:
    """An API key's idle timeout in seconds; None when the key has none (the default applies)."""
    return minutes * 60 if minutes is not None else None


def effective_idle_seconds(timeout_seconds: int | None) -> int:
    """The idle timeout that applies: the given one, else DEFAULT_SESSION_IDLE_SECONDS."""
    return timeout_seconds if timeout_seconds else DEFAULT_SESSION_IDLE_SECONDS


def is_idle(last_activity_at: datetime, timeout_seconds: int, now: datetime) -> bool:
    """Whether a Session last active at `last_activity_at` has been idle for longer than `timeout_seconds`."""
    return now - last_activity_at > timedelta(seconds=timeout_seconds)
