"""Server-related enumeration definitions."""

from enum import StrEnum


class TransportType(StrEnum):
    """Supported MCP transport protocols."""

    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable-http"


class ServerHealthStatus(StrEnum):
    """MCP server connectivity and health statuses."""

    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    CONNECTING = "CONNECTING"
    DISCONNECTED = "DISCONNECTED"
