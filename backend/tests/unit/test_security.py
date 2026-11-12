"""Unit tests for security controls."""

import asyncio
import socket

import pytest

from app.core.exceptions import ForbiddenError
from app.helpers.security import (
    mask_sensitive_headers,
    sanitize_environment,
    validate_http_url,
    validate_http_url_resolved,
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


def test_validate_http_url_blocks_mapped_and_unspecified_addresses():
    """IPv4-mapped IPv6 loopback and the unspecified address must not slip through."""
    with pytest.raises(ForbiddenError):
        validate_http_url("http://[::ffff:127.0.0.1]:8000/mcp", allow_private=False)

    with pytest.raises(ForbiddenError):
        validate_http_url("http://0.0.0.0:8000/mcp", allow_private=False)


def _resolve_to(monkeypatch: pytest.MonkeyPatch, *addresses: str) -> list[str]:
    """Make the running loop resolve every hostname to `addresses`; returns the hostnames looked up."""
    lookups: list[str] = []

    async def fake_getaddrinfo(host, port, **kwargs):
        lookups.append(host)
        return [(socket.AF_INET6 if ":" in addr else socket.AF_INET, socket.SOCK_STREAM, 6, "", (addr, port)) for addr in addresses]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", fake_getaddrinfo)
    return lookups


async def test_resolved_url_rejects_public_name_pointing_at_private_address(monkeypatch):
    _resolve_to(monkeypatch, "10.0.0.5")

    with pytest.raises(ForbiddenError) as err:
        await validate_http_url_resolved("https://mcp.example.com/api", allow_private=False)
    assert err.value.details["ip"] == "10.0.0.5"


async def test_resolved_url_allows_public_address(monkeypatch):
    lookups = _resolve_to(monkeypatch, "93.184.216.34")

    url = "https://mcp.example.com/api"
    assert await validate_http_url_resolved(url, allow_private=False) == url
    assert lookups == ["mcp.example.com"]


async def test_resolved_url_rejects_when_any_address_is_private(monkeypatch):
    _resolve_to(monkeypatch, "93.184.216.34", "192.168.1.10")

    with pytest.raises(ForbiddenError):
        await validate_http_url_resolved("https://mcp.example.com/api", allow_private=False)


async def test_resolved_url_rejects_ipv4_mapped_loopback(monkeypatch):
    _resolve_to(monkeypatch, "::ffff:127.0.0.1")

    with pytest.raises(ForbiddenError):
        await validate_http_url_resolved("https://mcp.example.com/api", allow_private=False)


async def test_resolved_url_skips_resolution_when_private_allowed(monkeypatch):
    lookups = _resolve_to(monkeypatch, "10.0.0.5")

    url = "http://internal.example.com/mcp"
    assert await validate_http_url_resolved(url, allow_private=True) == url
    assert lookups == []


async def test_resolved_url_tolerates_unresolvable_host(monkeypatch):
    async def failing_getaddrinfo(host, port, **kwargs):
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", failing_getaddrinfo)

    url = "https://does-not-exist.example.com/mcp"
    assert await validate_http_url_resolved(url, allow_private=False) == url


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
