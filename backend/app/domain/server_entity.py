"""Server domain entity."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.enums.server_enum import ServerAuthType, ServerHealthStatus, TransportType
from app.schemas.connection_schema import HttpConfig, StdioConfig


@dataclass
class ServerEntity:
    """Core domain entity representing an MCP Server registration."""

    name: str
    transport: TransportType
    user_id: UUID  # the owning account
    id: UUID = field(default_factory=uuid4)
    description: str | None = None
    stdio_config: StdioConfig | None = None
    http_config: HttpConfig | None = None
    enabled: bool = True
    auth_type: ServerAuthType = ServerAuthType.NONE
    oauth_provider_id: str | None = None  # catalog id when auth_type is OAUTH
    health_status: ServerHealthStatus = ServerHealthStatus.UNKNOWN
    last_connected_at: datetime | None = None
    last_health_check_at: datetime | None = None
    discovered_tool_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
