"""Schemas for per-API-key tool visibility (ADR-0007)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyToolResponse(BaseModel):
    """One of a server's tools, with whether the API key can see and run it."""

    tool_id: UUID = Field(..., description="Tool ID (UUID); a new one each time the server's tools are re-discovered")
    name: str = Field(..., description="Tool name exposed by the MCP server")
    description: str | None = Field(default=None, description="Tool description provided by server")
    enabled: bool = Field(..., description="Whether the API key can find this tool with SEARCH_TOOLS and run it")


class ApiKeyToolUpdateRequest(BaseModel):
    """Show or hide one tool for an API key."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(..., description="true shows the tool to the key; false hides it from search and blocks running it")


class ApiKeyToolUpdateResponse(BaseModel):
    tool_name: str
    enabled: bool
