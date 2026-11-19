"""Error message formatting and exception unwrapping helpers."""

from mcp.client.auth import OAuthFlowError


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


def find_oauth_error(exc: BaseException | None) -> OAuthFlowError | None:
    """The OAuthFlowError inside `exc` (directly, in an exception group, or in its cause/context chain)."""
    seen: set[int] = set()
    stack: list[BaseException] = [exc] if exc is not None else []
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, OAuthFlowError):
            return current
        if isinstance(current, BaseExceptionGroup):
            stack.extend(current.exceptions)
        for linked in (current.__cause__, current.__context__):
            if linked is not None:
                stack.append(linked)
    return None
