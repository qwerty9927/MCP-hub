"""Custom exceptions for MCP Hub backend."""

from typing import Any


class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        status_code: int = 500,
        details: Any = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class BadRequestError(AppError):
    """Raised when a request is invalid or cannot be processed in the current state (HTTP 400)."""

    def __init__(self, message: str = "Bad request", details: Any = None):
        super().__init__(message=message, status_code=400, details=details)


class ForbiddenError(AppError):
    """Raised when an operation is forbidden or violates security policy (HTTP 403)."""

    def __init__(self, message: str = "Access forbidden", details: Any = None):
        super().__init__(message=message, status_code=403, details=details)


class NotFoundError(AppError):
    """Raised when a requested resource is not found (HTTP 404)."""

    def __init__(self, message: str = "Resource not found", details: Any = None):
        super().__init__(message=message, status_code=404, details=details)


class ConflictError(AppError):
    """Raised when a resource conflict occurs (HTTP 409)."""

    def __init__(self, message: str = "Resource conflict", details: Any = None):
        super().__init__(message=message, status_code=409, details=details)


class ValidationError(AppError):
    """Raised when request or payload validation fails (HTTP 422)."""

    def __init__(self, message: str = "Validation failed", details: Any = None):
        super().__init__(message=message, status_code=422, details=details)


class InternalServerError(AppError):
    """Raised when an internal error or execution failure occurs (HTTP 500)."""

    def __init__(self, message: str = "Internal server error", details: Any = None):
        super().__init__(message=message, status_code=500, details=details)


class BadGatewayError(AppError):
    """Raised when an upstream service connection or communication fails (HTTP 502)."""

    def __init__(
        self,
        message: str = "Bad gateway or upstream connection failed",
        details: Any = None,
    ):
        super().__init__(message=message, status_code=502, details=details)


class GatewayTimeoutError(AppError):
    """Raised when an upstream service or operation exceeds timeout limit (HTTP 504)."""

    def __init__(
        self,
        message: str = "Gateway timeout or operation timed out",
        details: Any = None,
    ):
        super().__init__(message=message, status_code=504, details=details)
