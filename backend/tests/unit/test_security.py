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


def _resolve_to(monkeypatch: pytest.MonkeyPatch, *addresses: str) -> list[str]:
    """Make the running loop resolve every hostname to `addresses`; returns the hostnames looked up."""
    lookups: list[str] = []

    async def fake_getaddrinfo(host, port, **kwargs):
        lookups.append(host)
        return [(socket.AF_INET6 if ":" in addr else socket.AF_INET, socket.SOCK_STREAM, 6, "", (addr, port)) for addr in addresses]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", fake_getaddrinfo)
    return lookups


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("python", ["-c", "import os; os.system('id')"]),
        ("python3", ["-Ic", "print(1)"]),
        ("python3", ["-cprint(1)"]),
        ("node", ["-e", "require('child_process').execSync('id')"]),
        ("node", ["--eval=process.exit()"]),
        ("node", ["-p", "1"]),
        ("node", ["--require", "/tmp/evil.js", "server.js"]),
        ("node", ["--import=data:text/javascript,1", "server.js"]),
        ("bun", ["--eval", "1"]),
        ("uv", ["run", "python", "-c", "print(1)"]),
        ("npx", ["-c", "id"]),
        ("npx", ["--call=id"]),
        # option values separated by a space must not end the scan
        ("node", ["--title", "x", "-e", "1"]),
        ("node", ["--input-type", "module", "--eval", "1"]),
        ("bun", ["--port", "1", "-e", "1"]),
        ("uv", ["run", "node", "--title", "x", "-e", "1"]),
        ("npx", ["-p", "cowsay", "-c", "id"]),
        ("npx", ["--package", "foo", "--call", "id"]),
        ("python", ["--check-hash-based-pycs", "always", "-c", "1"]),
        ("python3", ["-W", "ignore", "-c", "1"]),
        # interpreters and shells reached through a runner
        ("uv", ["run", "python3.13t", "-c", "1"]),
        ("uv", ["run", "pypy3", "-c", "1"]),
        ("uv", ["run", "sh", "-c", "id"]),
        ("docker", ["run", "--rm", "alpine", "bash", "-lc", "id"]),
        ("npx", ["-y", "some-pkg", "node", "-e", "1"]),
        # a runner's option value that looks like an interpreter does not end the scan
        ("uv", ["run", "--with", "python3", "node", "-e", "1"]),
        ("uv", ["run", "-w", "python3", "node", "-e", "1"]),
        ("uv", ["run", "python", "-m", "x", "node", "-e", "1"]),
    ],
)
def test_validate_stdio_command_rejects_inline_code(command, args):
    """Flags that make an interpreter run code given on the command line must be rejected."""
    with pytest.raises(ForbiddenError, match="inline code"):
        validate_stdio_command(command, args)


def test_validate_stdio_command_allows_flags_of_other_programs():
    """Flags are judged per program: docker's -e/-p and a script's own options are not interpreter flags."""
    validate_stdio_command("docker", ["run", "-i", "--rm", "-e", "API_KEY", "-p", "8080:80", "mcp/fetch"])
    validate_stdio_command("python", ["server.py", "-c", "config.toml"])
    validate_stdio_command("npx", ["-y", "@modelcontextprotocol/server-filesystem", "/data"])
    validate_stdio_command("python3", ["-u", "-m", "demo"])


def test_validate_stdio_command_refused_when_stdio_disabled(monkeypatch):
    """With ALLOW_STDIO_SERVERS off, no stdio command is accepted, even an allowlisted one."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ALLOW_STDIO_SERVERS", False)
    with pytest.raises(ForbiddenError, match="disabled"):
        validate_stdio_command("python", ["server.py"])


@pytest.mark.parametrize(
    "key",
    [
        "LD_PRELOAD",
        "DYLD_INSERT_LIBRARIES",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "PYTHONWARNINGS",
        "NODE_OPTIONS",
        "NODE_REPL_EXTERNAL_MODULE",
        "NODE_EXTRA_CA_CERTS",
        "PATH",
        "path",
        "HOME",
        "BASH_ENV",
        "npm_config_node_options",
        "OPENSSL_CONF",
        "OPENSSL_MODULES",
        "GCONV_PATH",
        "GLIBC_TUNABLES",
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "XDG_CONFIG_HOME",
    ],
)
def test_validate_stdio_environment_rejects_loader_variables(key):
    """Variables that change what code a child process loads must be rejected."""
    from app.helpers.security import validate_stdio_environment

    with pytest.raises(ForbiddenError, match=key):
        validate_stdio_environment({key: "x"})


def test_validate_stdio_environment_allows_ordinary_variables():
    from app.helpers.security import validate_stdio_environment

    validate_stdio_environment({"GITHUB_TOKEN": "x", "API_KEY": "y", "LOG_LEVEL": "debug"})
    # Common in real MCP server configs, and they do not change which code runs
    validate_stdio_environment(
        {
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "UV_CACHE_DIR": "/tmp/uv",
            "NPM_CONFIG_REGISTRY": "https://r",
            "DOCKER_HOST": "unix:///x",
        }
    )
    validate_stdio_environment(None)


def test_sanitize_environment_drops_loader_variables():
    """A server stored before the env check existed must still not pass loader variables to its process."""
    sanitized = sanitize_environment({"LD_PRELOAD": "/tmp/x.so", "NODE_OPTIONS": "--require /tmp/x", "API_KEY": "k"})
    assert "LD_PRELOAD" not in sanitized
    assert "NODE_OPTIONS" not in sanitized
    assert sanitized["API_KEY"] == "k"


@pytest.mark.parametrize(
    "name",
    ["X-Auth-Token", "X-Goog-Api-Key", "Private-Token", "X-Figma-Token", "X-Access-Key", "Client-Secret", "X-Session-Token", "X-Password"],
)
def test_mask_sensitive_headers_masks_credential_like_names(name):
    """Any header whose name looks like a credential is masked, not only a fixed list."""
    assert mask_sensitive_headers({name: "s3cr3t"}) == {name: "********"}


def test_mask_sensitive_headers_keeps_ordinary_headers():
    headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "mcp-hub", "X-Region": "eu"}
    assert mask_sensitive_headers(headers) == headers


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost./mcp",
        "http://LOCALHOST/mcp",
        "http://api.localhost/mcp",
        "http://127.1/mcp",
        "http://0x7f.1/mcp",
        "http://0x7f000001/mcp",
        "http://2130706433/mcp",
        "http://017700000001/mcp",
        "http://10.1/mcp",
        "http://169.254.169.254./latest/meta-data",
        "http://internal.service.internal./mcp",
    ],
)
def test_validate_http_url_blocks_alternative_spellings_of_private_hosts(url):
    with pytest.raises(ForbiddenError):
        validate_http_url(url, allow_private=False)


@pytest.mark.parametrize("url", ["https://cafe.be/mcp", "https://mcp.example.com./mcp", "https://1password.com/mcp", "https://8.8.8.8/mcp"])
def test_validate_http_url_still_allows_public_hosts(url):
    assert validate_http_url(url, allow_private=False) == url


def test_production_refuses_private_network_http():
    from pydantic import ValidationError

    from app.core.config import Settings, get_settings

    values = get_settings().model_dump()
    with pytest.raises(ValidationError, match="ALLOW_PRIVATE_NETWORK_HTTP"):
        Settings(**{**values, "ENVIRONMENT": "production", "ALLOW_PRIVATE_NETWORK_HTTP": True})
    Settings(**{**values, "ENVIRONMENT": "production", "ALLOW_PRIVATE_NETWORK_HTTP": False})
    Settings(**{**values, "ENVIRONMENT": "development", "ALLOW_PRIVATE_NETWORK_HTTP": True})


@pytest.mark.parametrize(
    "args",
    [
        ["run", "--privileged", "mcp/fetch"],
        ["run", "-v", "/:/host", "mcp/fetch"],
        ["run", "--volume=/var/run/docker.sock:/var/run/docker.sock", "mcp/fetch"],
        ["run", "--mount", "type=bind,src=/,dst=/host", "mcp/fetch"],
        ["run", "--network", "host", "mcp/fetch"],
        ["run", "--net=host", "mcp/fetch"],
        ["run", "--pid=host", "mcp/fetch"],
        ["run", "--cap-add", "SYS_ADMIN", "mcp/fetch"],
        ["run", "--device", "/dev/sda", "mcp/fetch"],
        ["run", "--security-opt", "seccomp=unconfined", "mcp/fetch"],
        ["run", "--userns=host", "mcp/fetch"],
    ],
)
def test_validate_stdio_command_rejects_docker_host_access(args):
    """docker flags that reach the host (mounts, privileged, host namespaces) would give root on the hub's host."""
    with pytest.raises(ForbiddenError, match="host"):
        validate_stdio_command("docker", args)


@pytest.mark.parametrize("url", ["http://[2002:7f00:1::]/mcp", "http://[64:ff9b::7f00:1]/mcp", "http://[64:ff9b::a9fe:a9fe]/latest"])
def test_validate_http_url_blocks_ipv6_forms_of_private_ipv4(url):
    with pytest.raises(ForbiddenError):
        validate_http_url(url, allow_private=False)


def test_sanitize_environment_logs_what_it_drops(caplog):
    caplog.set_level("WARNING", logger="mcp_hub")
    sanitize_environment({"LD_PRELOAD": "/tmp/x.so", "API_KEY": "k"})
    assert any("LD_PRELOAD" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("subcommand", ["exec", "cp", "compose", "build"])
def test_validate_stdio_command_allows_only_docker_run(subcommand):
    with pytest.raises(ForbiddenError):
        validate_stdio_command("docker", [subcommand, "-i", "other"])
