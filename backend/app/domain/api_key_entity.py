"""API key domain entity."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass
class ApiKeyEntity:
    """A revocable credential an MCP client uses to call the hub's /mcp endpoint on behalf of an account."""

    user_id: UUID
    name: str
    key_prefix: str
    key_hash: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    # Minutes without a tool call after which a Session opened with this key is completed; None = the default.
    # Not the key's expiry.
    session_idle_minutes: int | None = None
