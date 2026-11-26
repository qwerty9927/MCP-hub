"""Constants for hub Sessions and the background job that completes idle ones (ADR-0003, ADR-0005)."""

# A Session opened by an API key with no idle timeout of its own is completed after this long without a tool call.
DEFAULT_SESSION_IDLE_SECONDS: int = 30 * 60

# Bounds for the idle timeout a user may set on an API key, in minutes (1 minute to 24 hours).
MIN_SESSION_IDLE_MINUTES: int = 1
MAX_SESSION_IDLE_MINUTES: int = 24 * 60

# A reused Session's last_activity_at is refreshed at most this often, so not every request writes.
ACTIVITY_REFRESH_SECONDS: int = 60

# `session_source` in Session metadata. Rows from before ADR-0004 may still say "transport".
SESSION_SOURCE_DERIVED: str = "derived"

MAX_USER_AGENT_LENGTH: int = 255
