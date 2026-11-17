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
    DISCONNECTED = "DISCONNECTED"
    NEEDS_AUTH = "NEEDS_AUTH"  # an OAuth server whose tokens can no longer be refreshed: the user must sign in again


class ServerAuthType(StrEnum):
    """How the hub authenticates to a server."""

    NONE = "none"  # no auth, or static headers in http_config
    OAUTH = "oauth"  # OAuth tokens held in server_oauth_credentials (ADR-0008)
