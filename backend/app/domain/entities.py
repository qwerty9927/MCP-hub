"""Domain entities for MCP Hub."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.schemas.server import HttpConfig, ServerHealthStatus, StdioConfig, TransportType


@dataclass
class ServerEntity:
    """Core domain entity representing an MCP Server registration."""

    name: str
    transport: TransportType
    id: UUID = field(default_factory=uuid4)
    description: str | None = None
    stdio_config: StdioConfig | None = None
    http_config: HttpConfig | None = None
    enabled: bool = True
    health_status: ServerHealthStatus = ServerHealthStatus.UNKNOWN
    last_connected_at: datetime | None = None
    last_health_check_at: datetime | None = None
    discovered_tool_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ToolEntity:
    """Core domain entity representing a discovered tool."""

    id: str
    server_id: UUID
    server_name: str
    name: str
    input_schema: dict[str, Any]
    description: str | None = None
    availability_status: str = "AVAILABLE"
    last_discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ExecutionEntity:
    """Core domain entity representing a tool execution record."""

    id: UUID
    server_id: UUID
    server_name: str
    tool_name: str
    arguments: dict[str, Any]
    is_error: bool
    duration_ms: float
    executed_at: datetime
    error_message: str | None = None
