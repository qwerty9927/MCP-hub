"""Security validation and sanitization helpers."""

import ipaddress
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError

# Sensitive environment variable keywords to mask or block
SENSITIVE_ENV_PATTERNS = [
    re.compile(r".*TOKEN.*", re.IGNORECASE),
    re.compile(r".*SECRET.*", re.IGNORECASE),
    re.compile(r".*PASSWORD.*", re.IGNORECASE),
    re.compile(r".*KEY.*", re.IGNORECASE),
    re.compile(r".*DATABASE_URL.*", re.IGNORECASE),
    re.compile(r".*CREDENTIAL.*", re.IGNORECASE),
]

# Sensitive HTTP headers
SENSITIVE_HEADER_NAMES = {
    "authorization",
    "x-api-key",
    "api-key",
    "cookie",
    "set-cookie",
    "proxy-authorization",
}

# Dangerous shell characters
DANGEROUS_SHELL_CHARS = {";", "&", "|", "`", "$", "\n", "\r", "\t", "<", ">", "\0"}


def validate_stdio_command(command: str, args: list[str] | None = None) -> None:
    """Validate stdio command and arguments against security policies.

    Prevents command injection and limits executables to an approved allowlist.
    """
    settings = get_settings()

    if not command or not command.strip():
        raise ForbiddenError("Executable command cannot be empty")

    cmd_stripped = command.strip()

    # Disallow dangerous shell characters in the command binary itself
    for char in DANGEROUS_SHELL_CHARS:
        if char in cmd_stripped:
            raise ForbiddenError(f"Command binary contains disallowed character: {char!r}")

    # Extract base name (e.g. '/opt/homebrew/bin/python3' -> 'python3')
    cmd_name = Path(cmd_stripped).name

    # Check against allowed executables
    allowed = set(settings.ALLOWED_STDIO_EXECUTABLES)
    # Check both full command and basename
    if cmd_stripped not in allowed and cmd_name not in allowed:
        raise ForbiddenError(
            f"Executable '{cmd_stripped}' is not in the approved stdio allowlist",
            details={"executable": cmd_stripped},
        )

    # Validate arguments for null bytes or suspicious characters
    if args:
        for arg in args:
            if "\0" in arg:
                raise ForbiddenError("Argument contains illegal null byte")


def sanitize_environment(custom_env: dict[str, str] | None, inherit_base: bool = True) -> dict[str, str]:
    """Sanitize environment variables passed to child stdio processes.

    Ensures host secrets are not leaked unintentionally to child processes.
    """
    # Start with a safe minimal system environment
    sanitized: dict[str, str] = {}
    if inherit_base:
        safe_keys = {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP"}
        for key in safe_keys:
            if key in os.environ:
                sanitized[key] = os.environ[key]

    if not custom_env:
        return sanitized

    for key, val in custom_env.items():
        # Prevent passing modified system secrets unless explicitly needed
        sanitized[str(key)] = str(val)

    return sanitized


def validate_http_url(url: str, allow_private: bool | None = None) -> str:
    """Validate remote URL for SSRF vulnerabilities."""
    if allow_private is None:
        allow_private = get_settings().ALLOW_PRIVATE_NETWORK_HTTP

    if not url or not url.strip():
        raise ForbiddenError("URL cannot be empty", details={"url": url})

    parsed = urlparse(url.strip())

    if parsed.scheme not in {"http", "https"}:
        raise ForbiddenError(
            f"Invalid scheme '{parsed.scheme}'. Only http and https are allowed",
            details={"url": url, "scheme": parsed.scheme},
        )

    if not parsed.hostname:
        raise ForbiddenError("Hostname is missing in URL", details={"url": url})

    hostname = parsed.hostname.lower()

    if not allow_private:
        # Check for localhost / loopback
        if hostname in {"localhost", "127.0.0.1", "::1"}:
            raise ForbiddenError(
                "Access to localhost/loopback is forbidden in production mode",
                details={"url": url},
            )

        # Check for IP address private ranges & cloud metadata
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ForbiddenError(
                    f"Access to private/local IP range {ip} is prohibited",
                    details={"url": url, "ip": str(ip)},
                )
            if str(ip) == "169.254.169.254":
                raise ForbiddenError(
                    "Access to cloud instance metadata endpoint is prohibited",
                    details={"url": url},
                )
        except ValueError:
            # Not a literal IP, it's a domain name
            if hostname.endswith(".local") or hostname.endswith(".internal"):
                raise ForbiddenError(
                    "Access to internal domain names is prohibited",
                    details={"url": url},
                ) from None

    return url.strip()


def mask_sensitive_headers(headers: dict[str, str] | None) -> dict[str, str]:
    """Mask values of sensitive headers like Authorization or API keys for safe API responses."""
    if not headers:
        return {}

    masked: dict[str, str] = {}
    for key, val in headers.items():
        if key.lower() in SENSITIVE_HEADER_NAMES:
            masked[key] = "********"
        else:
            masked[key] = val
    return masked
