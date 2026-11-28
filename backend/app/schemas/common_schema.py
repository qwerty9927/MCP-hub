"""Common schemas and response models."""

from pydantic import BaseModel, Field


class PaginatedResponse[T](BaseModel):
    """Standard pagination envelope."""

    items: list[T] = Field(description="List of records for the current page")
    total: int = Field(description="Total number of items matching filter criteria")
    page: int = Field(default=1, description="Current page number (1-indexed)")
    page_size: int = Field(default=20, description="Number of items per page")
    total_pages: int = Field(description="Total number of pages")


class ErrorDetail(BaseModel):
    """Detailed error object."""

    code: str | int = Field(description="Machine-readable error code or HTTP status code")
    message: str = Field(description="Human-readable error description")
    details: dict | list | str | None = Field(default=None, description="Optional error metadata")
    correlation_id: str | None = Field(default=None, description="Request correlation ID for tracing")


class ErrorResponse(BaseModel):
    """Consistent API error response structure."""

    error: ErrorDetail


# Error responses every /api/v1 route can return, all in the ErrorResponse envelope. Declaring 422 here also replaces
# FastAPI's default HTTPValidationError, which does not match the body the hub actually sends.
ERROR_RESPONSES: dict[int | str, dict] = {
    400: {"model": ErrorResponse, "description": "Bad request"},
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired credentials"},
    403: {"model": ErrorResponse, "description": "Forbidden by policy"},
    404: {"model": ErrorResponse, "description": "Not found"},
    422: {"model": ErrorResponse, "description": "Request validation failed"},
    500: {"model": ErrorResponse, "description": "Unexpected server error"},
}
