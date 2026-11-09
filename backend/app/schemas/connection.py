"""Connection configuration schemas for MCP transports."""

from pydantic import BaseModel, Field


class StdioConfig(BaseModel):
    """Configuration for local subprocess stdio transport."""

    command: str = Field(..., description="Executable name or path (e.g. 'python', 'node')")
    args: list[str] = Field(default_factory=list, description="Command-line arguments")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")


class HttpConfig(BaseModel):
    """Configuration for remote Streamable HTTP transport."""

    url: str = Field(
        ..., description="Full Streamable HTTP endpoint URL (e.g. 'http://localhost:8000/mcp')"
    )
    headers: dict[str, str] = Field(default_factory=dict, description="Custom HTTP headers")


class ConnectionConfigRead(BaseModel):
    """Sanitized transport configuration for API responses (no secrets)."""

    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
