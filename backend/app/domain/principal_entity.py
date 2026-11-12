"""Authenticated caller identity."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Principal:
    """Who is making a request: an account, and the API key it presented (None for a console login token)."""

    user_id: UUID
    api_key_id: UUID | None = None
