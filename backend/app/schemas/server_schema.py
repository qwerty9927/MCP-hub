"""MCP Server configuration and status schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.enums.server_enum import ServerHealthStatus, TransportType
from app.helpers.security import mask_sensitive_headers, validate_http_url, validate_stdio_command
from app.schemas.connection_schema import ConnectionConfigResponse, HttpConfig, StdioConfig


class ServerBase(BaseModel):
    """Common properties of an MCP Server."""

    name: str = Field(..., min_length=1, max_length=100, description="Unique human-readable server name")
    description: str | None = Field(default=None, max_length=500, description="Server description")
    transport: TransportType = Field(..., description="Transport protocol: 'stdio' or 'streamable-http'")
    enabled: bool = Field(default=True, description="Whether this server is enabled for tool execution")


class ServerCreateRequest(ServerBase):
    """Schema for registering a new MCP Server."""

    stdio_config: StdioConfig | None = Field(default=None, description="Configuration for stdio transport")
    http_config: HttpConfig | None = Field(default=None, description="Configuration for streamable-http transport")

    @model_validator(mode="after")
    def validate_transport_configuration(self) -> "ServerCreateRequest":
        if self.transport == TransportType.STDIO:
            if not self.stdio_config:
                raise ValueError("stdio_config is required when transport is 'stdio'")
            validate_stdio_command(self.stdio_config.command, self.stdio_config.args)
        elif self.transport == TransportType.STREAMABLE_HTTP:
            if not self.http_config:
                raise ValueError("http_config is required when transport is 'streamable-http'")
            validate_http_url(self.http_config.url)
        return self


# Backward-compatible alias
ServerCreate = ServerCreateRequest


class ServerUpdateRequest(BaseModel):
    """Schema for updating an existing MCP Server configuration."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    transport: TransportType | None = None
    stdio_config: StdioConfig | None = None
    http_config: HttpConfig | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def validate_partial_transport(self) -> "ServerUpdateRequest":
        if self.transport == TransportType.STDIO and self.stdio_config:
            validate_stdio_command(self.stdio_config.command, self.stdio_config.args)
        elif self.transport == TransportType.STREAMABLE_HTTP and self.http_config:
            validate_http_url(self.http_config.url)
        elif self.stdio_config:
            validate_stdio_command(self.stdio_config.command, self.stdio_config.args)
        elif self.http_config:
            validate_http_url(self.http_config.url)
        return self


# Backward-compatible alias
ServerUpdate = ServerUpdateRequest


class ServerResponse(BaseModel):
    """Server representation returned in API responses."""

    id: UUID
    name: str
    description: str | None = None
    transport: TransportType
    connection_config: ConnectionConfigResponse
    enabled: bool
    health_status: ServerHealthStatus
    last_connected_at: datetime | None = None
    last_health_check_at: datetime | None = None
    discovered_tool_count: int = 0
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, server: Any) -> "ServerResponse":
        """Convert a server domain entity or dictionary into ServerResponse with masked headers."""
        if isinstance(server, dict):
            transport = server["transport"]
            stdio_cfg = server.get("stdio_config") or {}
            http_cfg = server.get("http_config") or {}
            headers = mask_sensitive_headers(http_cfg.get("headers")) if http_cfg else None

            config_read = ConnectionConfigResponse(
                command=stdio_cfg.get("command") if transport == TransportType.STDIO else None,
                args=stdio_cfg.get("args") if transport == TransportType.STDIO else None,
                url=http_cfg.get("url") if transport == TransportType.STREAMABLE_HTTP else None,
                headers=headers if transport == TransportType.STREAMABLE_HTTP else None,
            )

            return cls(
                id=server["id"],
                name=server["name"],
                description=server.get("description"),
                transport=transport,
                connection_config=config_read,
                enabled=server["enabled"],
                health_status=server["health_status"],
                last_connected_at=server.get("last_connected_at"),
                last_health_check_at=server.get("last_health_check_at"),
                discovered_tool_count=server.get("discovered_tool_count", 0),
                created_at=server["created_at"],
                updated_at=server["updated_at"],
            )

        # For object attributes
        headers = mask_sensitive_headers(server.http_config.headers) if hasattr(server, "http_config") and server.http_config else None
        config_read = ConnectionConfigResponse(
            command=server.stdio_config.command if server.transport == TransportType.STDIO and server.stdio_config else None,
            args=server.stdio_config.args if server.transport == TransportType.STDIO and server.stdio_config else None,
            url=server.http_config.url if server.transport == TransportType.STREAMABLE_HTTP and server.http_config else None,
            headers=headers if server.transport == TransportType.STREAMABLE_HTTP else None,
        )

        return cls(
            id=server.id,
            name=server.name,
            description=server.description,
            transport=server.transport,
            connection_config=config_read,
            enabled=server.enabled,
            health_status=server.health_status,
            last_connected_at=server.last_connected_at,
            last_health_check_at=server.last_health_check_at,
            discovered_tool_count=server.discovered_tool_count,
            created_at=server.created_at,
            updated_at=server.updated_at,
        )


class ServerTestResponse(BaseModel):
    """Response returned by connection test endpoint."""

    success: bool
    message: str
    tools_count: int = 0
    latency_ms: float = 0.0
