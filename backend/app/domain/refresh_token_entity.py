"""Console refresh token domain entity (ADR-0009)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass
class RefreshTokenEntity:
    """One link in a console sign-in's chain of refresh tokens. Only the token's hash is stored.

    Every login starts a family; each refresh marks the presented token used and adds its successor to the same
    family. Presenting a used token again is reuse, and revokes the whole family.
    """

    user_id: UUID
    family_id: UUID
    token_hash: str
    expires_at: datetime
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    used_at: datetime | None = None
    revoked_at: datetime | None = None
