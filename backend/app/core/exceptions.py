"""Custom exceptions for MCP Hub backend."""

from typing import Any


class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, status_code: int = 500, details: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(message=message, status_code=404, details=details)


class ServerNotFoundError(NotFoundError):
    """Raised when an MCP server configuration is not found."""

    def __init__(self, server_id: str):
        super().__init__(
            message=f"Server with id '{server_id}' not found",
            details={"server_id": server_id},
        )


class ToolNotFoundError(NotFoundError):
    """Raised when a requested tool is not found."""

    def __init__(self, tool_name: str, server_id: str | None = None):
        msg = (
            f"Tool '{tool_name}' not found on server '{server_id}'"
            if server_id
            else f"Tool '{tool_name}' not found"
        )
        super().__init__(message=msg, details={"tool_name": tool_name, "server_id": server_id})


class ExecutionNotFoundError(NotFoundError):
    """Raised when an execution history record is not found."""

    def __init__(self, execution_id: str):
        super().__init__(
            message=f"Execution with id '{execution_id}' not found",
            details={"execution_id": execution_id},
        )


class ConflictError(AppError):
    """Raised when a resource already exists or conflict occurs."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(message=message, status_code=409, details=details)


class ServerAlreadyExistsError(ConflictError):
    """Raised when a server with the same name already exists."""

    def __init__(self, name: str):
        super().__init__(
            message=f"A server with name '{name}' already exists",
            details={"name": name},
        )


class AppValidationError(AppError):
    """Raised when validation fails."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(message=message, status_code=422, details=details)


class SecurityViolationError(AppError):
    """Raised when a security policy is violated."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(message=message, status_code=403, details=details)


class DisallowedExecutableError(SecurityViolationError):
    """Raised when an unapproved executable is requested for stdio transport."""

    def __init__(self, executable: str):
        super().__init__(
            message=f"Executable '{executable}' is not in the approved stdio allowlist",
            details={"executable": executable},
        )


class SSRFSecurityError(SecurityViolationError):
    """Raised when a remote URL targets a restricted network destination."""

    def __init__(self, url: str, reason: str):
        super().__init__(
            message=f"SSRF Protection: URL '{url}' is restricted: {reason}",
            details={"url": url, "reason": reason},
        )


class ServerDisabledError(AppError):
    """Raised when an action is attempted on a disabled server."""

    def __init__(self, server_id: str):
        super().__init__(
            message=f"Server '{server_id}' is disabled. Enable it before performing this operation.",
            status_code=400,
            details={"server_id": server_id},
        )


class ServerConnectionError(AppError):
    """Raised when connection to an MCP server fails."""

    def __init__(self, server_id: str, reason: str):
        super().__init__(
            message=f"Failed to connect to server '{server_id}': {reason}",
            status_code=502,
            details={"server_id": server_id, "reason": reason},
        )


class ExecutionTimeoutError(AppError):
    """Raised when tool execution exceeds timeout limit."""

    def __init__(self, tool_name: str, timeout_seconds: float):
        super().__init__(
            message=f"Tool '{tool_name}' execution timed out after {timeout_seconds} seconds",
            status_code=504,
            details={"tool_name": tool_name, "timeout_seconds": timeout_seconds},
        )


class ToolExecutionError(AppError):
    """Raised when tool execution encounters an error."""

    def __init__(self, tool_name: str, reason: str, details: Any = None):
        super().__init__(
            message=f"Execution error for tool '{tool_name}': {reason}",
            status_code=500,
            details=details or {"tool_name": tool_name, "reason": reason},
        )
