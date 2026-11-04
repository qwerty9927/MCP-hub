"""Unit tests for security controls."""

import pytest

from app.core.exceptions import ForbiddenError
from app.helpers.security import (
    mask_sensitive_headers,
    sanitize_environment,
    validate_http_url,
    validate_stdio_command,
)


def test_validate_stdio_command_allowed():
    """Approved executables should pass validation."""
    validate_stdio_command("python", ["script.py"])
    validate_stdio_command("python3", ["-m", "demo"])
    validate_stdio_command("uv", ["run", "server.py"])


def test_validate_stdio_command_disallowed():
    """Unapproved executables should raise ForbiddenError."""
    with pytest.raises(ForbiddenError):
        validate_stdio_command("rm", ["-rf", "/"])

    with pytest.raises(ForbiddenError):
        validate_stdio_command("/bin/bash", ["-c", "whoami"])

    with pytest.raises(ForbiddenError):
        validate_stdio_command("nc", ["-e", "/bin/sh"])


def test_validate_stdio_command_injection_chars():
    """Dangerous characters in the executable command should raise ForbiddenError."""
    with pytest.raises(ForbiddenError):
        validate_stdio_command("python3; rm -rf /")

    with pytest.raises(ForbiddenError):
        validate_stdio_command("python3 | cat")

    with pytest.raises(ForbiddenError):
        validate_stdio_command("python3`whoami`")


def test_validate_stdio_null_byte_in_args():
    """Null bytes in args must be rejected."""
    with pytest.raises(ForbiddenError):
        validate_stdio_command("python3", ["arg1\0evil"])


def test_sanitize_environment():
    """System environment should be safely sanitized."""
    raw_env = {"MY_CUSTOM_VAR": "value123"}
    sanitized = sanitize_environment(raw_env)
    assert sanitized["MY_CUSTOM_VAR"] == "value123"
    assert "PATH" in sanitized


def test_validate_http_url_valid():
    """Valid HTTP/HTTPS URLs should pass."""
    url = "https://mcp.example.com/api"
    assert validate_http_url(url) == url


def test_validate_http_url_invalid_scheme():
    """Non-HTTP schemes should be rejected."""
    with pytest.raises(ForbiddenError):
        validate_http_url("file:///etc/passwd")

    with pytest.raises(ForbiddenError):
        validate_http_url("gopher://127.0.0.1:70")

    with pytest.raises(ForbiddenError):
        validate_http_url("ftp://example.com/data")


def test_validate_http_url_ssrf_protection():
    """Private IP ranges and localhost should be blocked when allow_private=False."""
    with pytest.raises(ForbiddenError):
        validate_http_url("http://127.0.0.1:8000/mcp", allow_private=False)

    with pytest.raises(ForbiddenError):
        validate_http_url("http://localhost:8080", allow_private=False)

    with pytest.raises(ForbiddenError):
        validate_http_url("http://169.254.169.254/latest/meta-data", allow_private=False)

    with pytest.raises(ForbiddenError):
        validate_http_url("http://192.168.1.10/admin", allow_private=False)


def test_mask_sensitive_headers():
    """Sensitive headers should be masked."""
    headers = {
        "Authorization": "Bearer super-secret-token",
        "X-Api-Key": "my-api-key",
        "Content-Type": "application/json",
        "User-Agent": "MCP-Client",
    }
    masked = mask_sensitive_headers(headers)
    assert masked["Authorization"] == "********"
    assert masked["X-Api-Key"] == "********"
    assert masked["Content-Type"] == "application/json"
    assert masked["User-Agent"] == "MCP-Client"
