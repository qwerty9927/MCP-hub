"""Common schemas and response models."""

from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    """Standard pagination envelope."""

    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20
    total_pages: int


class ErrorDetail(BaseModel):
    """Detailed error object."""

    code: str | int
    message: str
    details: dict | list | str | None = None
    correlation_id: str | None = None


class ErrorResponse(BaseModel):
    """Consistent API error response structure."""

    error: ErrorDetail
