"""Schemas for connecting hosted MCP servers with OAuth (ADR-0008)."""

from uuid import UUID

from pydantic import BaseModel, Field


class OAuthProviderResponse(BaseModel):
    """A catalog provider as the console shows it."""

    id: str
    name: str
    description: str
    category: str
    mcp_url: str
    docs_url: str | None = None
    logo: str | None = None
    available: bool = Field(..., description="False when the provider needs an OAuth app the admin has not configured")
    setup_hint: str | None = Field(default=None, description="What the admin must configure when not available")
    connected_count: int = Field(default=0, description="How many of the caller's servers use this provider")


class OAuthConnectRequest(BaseModel):
    """Start connecting a provider."""

    provider_id: str = Field(..., min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100, description="Server name; defaults to the provider id")


class OAuthConnectResponse(BaseModel):
    """Where to send the user to sign in; or, for a server that needed no sign-in, the server already created."""

    authorization_url: str | None = None
    state: str | None = None
    server_id: UUID | None = None
