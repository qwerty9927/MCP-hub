"""Error message formatting and exception unwrapping helpers."""


def format_mcp_error(exc: BaseException) -> str:
    """Extract a concise, human-readable error string from nested ExceptionGroups and MCPErrors."""
    current: BaseException = exc
    while isinstance(current, BaseExceptionGroup) and current.exceptions:
        current = current.exceptions[0]

    # Handle McpError from MCP SDK
    if hasattr(current, "error") and hasattr(current.error, "message"):
        code = getattr(current.error, "code", None)
        code_suffix = f" [code {code}]" if code else ""
        return f"{current.error.message}{code_suffix}"

    message = str(current).strip()
    return message if message else type(current).__name__
