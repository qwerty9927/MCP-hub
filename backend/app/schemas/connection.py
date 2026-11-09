"""Connection configuration schemas for MCP transports."""

from pydantic import BaseModel, Field


class StdioConfig(BaseModel):
    """Configuration for local subprocess stdio transport."""

    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class HttpConfig(BaseModel):
    """Configuration for remote Streamable HTTP transport."""

    url: str
    headers: dict[str, str] = Field(default_factory=dict)


class ConnectionConfigRead(BaseModel):
    """Sanitized transport configuration for API responses (no secrets)."""

    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
