"""In-memory stand-in for a downstream MCP Server, at the ConnectionManager seam."""

import asyncio
from typing import Any

import mcp.types as mcp_types

from app.core.exceptions import GatewayTimeoutError
from app.domain.server_entity import ServerEntity
from app.services.connection_manager import ConnectionManager

ADD_SCHEMA = {
    "type": "object",
    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
    "required": ["a", "b"],
}

DOWNSTREAM_TOOLS = [
    mcp_types.Tool(name="add", description="Add two numbers", input_schema=ADD_SCHEMA),
    mcp_types.Tool(name="explode", description="Reports a tool error", input_schema={"type": "object"}),
    mcp_types.Tool(name="silent_error", description="Reports an error without text", input_schema={"type": "object"}),
    mcp_types.Tool(name="hang", description="Times out", input_schema={"type": "object"}),
    mcp_types.Tool(name="cancel", description="Gets cancelled", input_schema={"type": "object"}),
]


class FakeDownstream(ConnectionManager):
    """In-memory stand-in for the downstream MCP Server, at the ConnectionManager seam."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self, server: ServerEntity, timeout: float | None = None) -> list[mcp_types.Tool]:
        return DOWNSTREAM_TOOLS

    async def call_tool(
        self,
        server: ServerEntity,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float | None = None,
    ) -> mcp_types.CallToolResult:
        self.calls.append((tool_name, arguments))
        if tool_name == "add":
            total = arguments["a"] + arguments["b"]
            return mcp_types.CallToolResult(
                content=[mcp_types.TextContent(type="text", text=str(total))],
                structured_content={"result": total},
                is_error=False,
            )
        if tool_name == "explode":
            return mcp_types.CallToolResult(
                content=[
                    mcp_types.TextContent(type="text", text="first line"),
                    mcp_types.TextContent(type="text", text="second line"),
                ],
                is_error=True,
            )
        if tool_name == "silent_error":
            return mcp_types.CallToolResult(content=[], is_error=True)
        if tool_name == "hang":
            raise GatewayTimeoutError(f"Tool '{tool_name}' execution timed out after 1 seconds")
        if tool_name == "cancel":
            raise asyncio.CancelledError()
        raise AssertionError(f"unexpected downstream tool {tool_name}")
