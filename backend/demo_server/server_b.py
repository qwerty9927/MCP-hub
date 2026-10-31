"""Second Demo MCP Server ('text-and-duplicate-tools') for testing multi-server aggregation.

Exposes tools:
- text_transform: Multi-mode text manipulation
- calculate: Duplicate tool name intentionally shared with demo_server/server.py
- json_prettify: Parses and formats JSON
"""

import json

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("text-tools-server")


@mcp.tool()
def text_transform(text: str, mode: str = "uppercase") -> str:
    """Transform text based on requested mode (uppercase, lowercase, reverse, word_count)."""
    mode_lower = mode.lower()
    if mode_lower == "uppercase":
        return text.upper()
    elif mode_lower == "lowercase":
        return text.lower()
    elif mode_lower == "reverse":
        return text[::-1]
    elif mode_lower == "word_count":
        return str(len(text.split()))
    return text


@mcp.tool()
def calculate(expression: str) -> str:
    """Duplicate-named tool to test multi-server qualified identifier resolution."""
    return f"[Server B Result for '{expression}']"


@mcp.tool()
def json_prettify(raw_json: str) -> str:
    """Validate and format a JSON string with 2-space indentation."""
    try:
        parsed = json.loads(raw_json)
        return json.dumps(parsed, indent=2)
    except Exception as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc


if __name__ == "__main__":
    mcp.run("stdio")
