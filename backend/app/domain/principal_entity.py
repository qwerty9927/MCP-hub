"""Authenticated caller identity."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Principal:
    """Who is making a request: an account, and the API key it presented (None for a console login token)."""

    user_id: UUID
    api_key_id: UUID | None = None
    # The API key's Session idle timeout in seconds (None = the default). Carried here because the key row is
    # already loaded to authenticate, so Session tracking needs no extra query.
    session_idle_seconds: int | None = None
