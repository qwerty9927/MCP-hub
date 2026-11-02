"""Reusable helper functions and utilities organized by responsibility."""

from app.core.logging import get_correlation_id, set_correlation_id
from app.helpers.errors import format_mcp_error
from app.helpers.security import (
    DANGEROUS_SHELL_CHARS,
    SENSITIVE_ENV_PATTERNS,
    SENSITIVE_HEADER_NAMES,
    mask_sensitive_headers,
    sanitize_environment,
    validate_http_url,
    validate_stdio_command,
)
from app.helpers.text import slugify
from app.helpers.validation import validate_tool_arguments

__all__ = [
    "DANGEROUS_SHELL_CHARS",
    "SENSITIVE_ENV_PATTERNS",
    "SENSITIVE_HEADER_NAMES",
    "format_mcp_error",
    "get_correlation_id",
    "mask_sensitive_headers",
    "sanitize_environment",
    "set_correlation_id",
    "slugify",
    "validate_http_url",
    "validate_stdio_command",
    "validate_tool_arguments",
]
