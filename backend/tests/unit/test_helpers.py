"""Unit tests for reusable helper modules."""

import pytest

from app.core.exceptions import AppValidationError
from app.helpers import (
    format_mcp_error,
    mask_sensitive_headers,
    sanitize_environment,
    slugify,
    validate_http_url,
    validate_stdio_command,
    validate_tool_arguments,
)


def test_text_slugify():
    """Verify string slugification handles whitespace, symbols, and defaults."""
    assert slugify("Github Tools") == "github_tools"
    assert slugify("Postgres-DB #1") == "postgres_db_1"
    assert slugify("  --- special ---  ") == "special"
    assert slugify("!!!") == "server"
    assert slugify("", default="custom_fallback") == "custom_fallback"
    assert slugify("Already_Snake_Case") == "already_snake_case"


def test_errors_format_mcp_error():
    """Verify error unwrapping handles normal exceptions, nested ExceptionGroups, and MCPErrors."""
    # Standard exception
    normal_err = ValueError("Something went wrong")
    assert format_mcp_error(normal_err) == "Something went wrong"

    # Nested ExceptionGroup
    class MockMCPError(Exception):
        def __init__(self, code, message):
            self.error = type("ErrorObj", (), {"code": code, "message": message})()

    mcp_err = MockMCPError(-32603, "Internal server error occurred")
    inner_group = ExceptionGroup("inner", [mcp_err])
    outer_group = ExceptionGroup("outer", [inner_group])

    formatted = format_mcp_error(outer_group)
    assert "Internal server error occurred" in formatted
    assert "[code -32603]" in formatted

    # Fallback to class name if empty message
    empty_err = Exception("")
    assert format_mcp_error(empty_err) == "Exception"


def test_validation_validate_tool_arguments():
    """Verify tool argument validation against JSON schemas."""
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1},
        },
        "required": ["query"],
    }

    # Valid arguments
    validate_tool_arguments({"query": "search term", "limit": 10}, schema, "search_tool")

    # Missing required field
    with pytest.raises(AppValidationError) as exc_info:
        validate_tool_arguments({"limit": 5}, schema, "search_tool")
    assert "Invalid arguments for tool 'search_tool'" in str(exc_info.value)
    assert "details" in exc_info.value.__dict__

    # Wrong type
    with pytest.raises(AppValidationError):
        validate_tool_arguments({"query": 12345}, schema, "search_tool")

    # No schema or empty schema
    validate_tool_arguments({"anything": True}, None, "no_schema_tool")
    validate_tool_arguments({"anything": True}, {}, "empty_schema_tool")


def test_helpers_package_exports():
    """Verify top-level app.helpers exports all expected helpers."""
    assert callable(slugify)
    assert callable(format_mcp_error)
    assert callable(validate_tool_arguments)
    assert callable(validate_stdio_command)
    assert callable(validate_http_url)
    assert callable(sanitize_environment)
    assert callable(mask_sensitive_headers)
