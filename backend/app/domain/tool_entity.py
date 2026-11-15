"""Tool domain entity."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID


@dataclass
class ToolEntity:
    """Core domain entity representing a discovered tool."""

    id: str
    server_id: UUID
    server_name: str
    name: str
    input_schema: dict[str, Any]
    user_id: UUID  # the owning account of the Server, copied here so catalog lookups can be scoped
    description: str | None = None
    availability_status: str = "AVAILABLE"
    last_discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
