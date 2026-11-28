"""Security validation and sanitization helpers."""

import asyncio
import ipaddress
import os
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError
from app.core.logging import logger

# Sensitive HTTP headers
SENSITIVE_HEADER_NAMES = {
    "authorization",
    "x-api-key",
    "api-key",
    "cookie",
    "set-cookie",
    "proxy-authorization",
}

# What a masked header value reads as in API responses
MASKED_HEADER_VALUE = "********"

# A header whose lower-cased name contains any of these is treated as a credential too (X-Auth-Token, Private-Token, ...)
SENSITIVE_HEADER_NAME_PARTS = ("auth", "token", "key", "secret", "password", "passwd", "cookie", "credential", "signature")

# Dangerous shell characters
DANGEROUS_SHELL_CHARS = {";", "&", "|", "`", "$", "\n", "\r", "\t", "<", ">", "\0"}


# Programs whose command-line flags can carry code to run.
# Python: python, python3, python3.12, python3.13t, pythonw, python3-debug, pypy, pypy3
_PYTHON_NAME = re.compile(r"^(python|pypy)(\d+(\.\d+)*)?[a-z]?(-dbg|-debug)?$")
_NODE_NAMES = frozenset({"node", "nodejs", "bun", "deno"})
_NPX_NAMES = frozenset({"npx", "pnpx", "bunx", "npm", "pnpm", "yarn"})  # package runners with a shell-command flag
_SHELL_NAMES = frozenset({"sh", "bash", "zsh", "dash", "ash", "ksh", "mksh", "fish"})
_CONTAINER_NAMES = frozenset({"docker", "podman"})
_RUNNER_NAMES = frozenset({"uv", "uvx", *_CONTAINER_NAMES})  # launch another program named in their arguments

_NODE_CODE_FLAGS = frozenset({"--eval", "--print", "--require", "--import", "--loader", "--experimental-loader"})
_NODE_CODE_LETTERS = frozenset("epr")  # -e, -p, -r, and clusters such as -pe
_NODE_VALUE_LETTERS = frozenset("Cc")  # node -C <condition>, bun -c <config>: the next argument is a value
_NPX_CODE_FLAGS = frozenset({"--call"})
_SHELL_CODE_FLAGS = frozenset({"--rcfile", "--init-file"})
_PYTHON_VALUE_LONG_FLAGS = frozenset({"--check-hash-based-pycs"})

# docker/podman run flags that reach the host: with any of them the container can act as root on the hub's host
_CONTAINER_HOST_FLAGS = frozenset(
    {"--privileged", "-v", "--volume", "--volumes-from", "--mount", "--device", "--cap-add", "--security-opt"}
)
_CONTAINER_HOST_NAMESPACE_FLAGS = frozenset({"--network", "--net", "--pid", "--ipc", "--uts", "--userns", "--cgroupns"})

# Variables a stdio server may not set: they make the process load other code (LD_PRELOAD, NODE_OPTIONS,
# PYTHONSTARTUP, OPENSSL_CONF, ...), change where it finds programs or its config (PATH, HOME, XDG_CONFIG_HOME),
# or change whom it trusts for downloads (proxies, CA bundles). Ordinary settings such as PYTHONUNBUFFERED,
# UV_CACHE_DIR or NPM_CONFIG_REGISTRY stay allowed.
_DANGEROUS_ENV_NAMES = frozenset(
    {
        "PATH",
        "HOME",
        "XDG_CONFIG_HOME",
        "BASH_ENV",
        "ENV",
        "SHELLOPTS",
        "BASHOPTS",
        "PS4",
        "PROMPT_COMMAND",
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "PYTHONINSPECT",
        "PYTHONUSERBASE",
        "PYTHONEXECUTABLE",
        "PYTHONPLATLIBDIR",
        "PYTHONBREAKPOINT",
        "PYTHONWARNINGS",
        "NODE_OPTIONS",
        "NODE_PATH",
        "NODE_EXTRA_CA_CERTS",
        "BUN_OPTIONS",
        "NPM_CONFIG_NODE_OPTIONS",
        "NPM_CONFIG_USERCONFIG",
        "NPM_CONFIG_GLOBALCONFIG",
        "NPM_CONFIG_SCRIPT_SHELL",
        "PERL5OPT",
        "PERL5LIB",
        "PERLLIB",
        "RUBYOPT",
        "RUBYLIB",
        "JAVA_TOOL_OPTIONS",
        "_JAVA_OPTIONS",
        "JDK_JAVA_OPTIONS",
        "GIT_SSH",
        "GIT_SSH_COMMAND",
        "GIT_EXEC_PATH",
        "GCONV_PATH",
        "LOCPATH",
        "NLSPATH",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
    }
)
_DANGEROUS_ENV_PREFIXES = ("LD_", "DYLD_", "OPENSSL_", "GLIBC_", "MALLOC_", "NODE_REPL_", "DENO_", "BUN_CONFIG_")
_DANGEROUS_ENV_SUFFIXES = ("_PROXY",)  # HTTP_PROXY, HTTPS_PROXY, ALL_PROXY, NO_PROXY


def validate_stdio_command(command: str, args: list[str] | None = None) -> None:
    """Validate stdio command and arguments against security policies.

    Refuses every command when ALLOW_STDIO_SERVERS is off, limits executables to an approved allowlist,
    and rejects interpreter flags that run code given on the command line (`python -c`, `node -e`, ...).

    The allowlist and flag checks narrow what a stdio server can do; they are not a sandbox. A runner such
    as npx, uv or docker can still fetch and run a package or image, so only let trusted accounts add stdio
    servers, or turn them off with ALLOW_STDIO_SERVERS=false.
    """
    settings = get_settings()

    if not settings.ALLOW_STDIO_SERVERS:
        raise ForbiddenError("Stdio servers are disabled on this hub (ALLOW_STDIO_SERVERS=false)")

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
        for argument in args:
            if "\0" in argument:
                raise ForbiddenError("Argument contains illegal null byte")

    flag = _inline_code_flag(cmd_name, args or [])
    if flag is not None:
        raise ForbiddenError(
            f"Argument '{flag}' would run inline code, which is not allowed for stdio servers",
            details={"executable": cmd_stripped, "argument": flag},
        )

    flag = _container_host_flag(cmd_name, args or [])
    if flag is not None:
        raise ForbiddenError(
            f"Argument '{flag}' would give the container access to the host, which is not allowed for stdio servers",
            details={"executable": cmd_stripped, "argument": flag},
        )


def _family(token: str) -> str | None:
    name = Path(token).name.lower()
    if _PYTHON_NAME.match(name):
        return "python"
    if name in _NODE_NAMES:
        return "node"
    if name in _NPX_NAMES:
        return "npx"
    if name in _SHELL_NAMES:
        return "shell"
    if name in _RUNNER_NAMES:
        return "runner"
    return None


def _short_letters(token: str) -> str:
    """The letters of a short-option cluster (`-Ic` -> `Ic`); empty for long options, `-` and non-options."""
    return token[1:] if token.startswith("-") and not token.startswith("--") else ""


def _takes_next_value(previous: str | None) -> bool:
    """Whether `previous` may be an option whose value is the next argument (`--title x`), not a flag.

    Any long option without `=` counts: reading a flag's neighbour as a value only means scanning further.
    """
    return previous is not None and previous.startswith("--") and "=" not in previous and previous != "--"


def _inline_code_flag(program: str, args: list[str]) -> str | None:
    """The first argument that makes an interpreter or shell run code from the command line, if any.

    Errs towards rejecting: an argument is read as the script (ending the interpreter's options) only when it
    cannot be the value of the option before it. Runners (uv, npx, docker) are followed into the program they
    launch, as in `uv run python -c ...` or `docker run img sh -c ...`. Python's options are parsed exactly, so a
    script's own `-c config.toml` is allowed; for node, bun, npx and shells a code flag before the script is enough.

    Once a runner is involved, finding a script does not end the scan: a runner's option value can look like an
    interpreter (`uv run --with python3 node -e ...`), so scanning goes on for the next program it might launch.
    """
    mode = _family(program)
    via_runner = mode in ("runner", "npx")
    previous: str | None = None
    skip_value = False
    for token in args:
        if skip_value:  # the value of the previous option
            skip_value, previous = False, token
            continue

        family = _family(token)
        if mode in (None, "runner") or (mode == "npx" and family not in (None, "runner")):
            mode = family or mode
            via_runner = via_runner or mode in ("runner", "npx")
            previous = token
            continue

        letters = _short_letters(token)
        name = token.split("=", 1)[0]
        is_operand = not token.startswith("-") or token == "-"

        if mode == "python":
            if token == "--" or is_operand:  # the script (or `--` before it): the rest belongs to the script
                if not via_runner:
                    return None
                mode, previous = family or "runner", token
                continue
            if name in _PYTHON_VALUE_LONG_FLAGS and "=" not in token:
                skip_value = True
            for position, letter in enumerate(letters):
                if letter == "c":
                    return token
                if letter in "WX":  # takes a value: the rest of the token, or the next argument
                    skip_value = position == len(letters) - 1
                    break
                if letter == "m":  # -m module: the rest belongs to the module
                    if not via_runner:
                        return None
                    mode = "runner"
                    break
        elif mode == "node":
            if token == "--" or (
                is_operand
                and token != "eval"
                and not _takes_next_value(previous)
                and not (previous and set(_short_letters(previous)) & _NODE_VALUE_LETTERS)
            ):  # the script
                if not via_runner:
                    return None
                mode, previous = family or "runner", token
                continue
            if is_operand:
                if token == "eval" and Path(previous or program).name.lower() == "deno":
                    return token
            elif name in _NODE_CODE_FLAGS or set(letters) & _NODE_CODE_LETTERS:
                return token
        elif mode == "npx":
            if name in _NPX_CODE_FLAGS or "c" in letters:
                return token
        elif mode == "shell":
            if token == "--" or (
                is_operand and not _takes_next_value(previous) and not (previous and set(_short_letters(previous)) & {"o", "O"})
            ):  # the script
                if not via_runner:
                    return None
                mode, previous = family or "runner", token
                continue
            if is_operand:
                pass
            elif name in _SHELL_CODE_FLAGS or "c" in letters:
                return token
        previous = token
    return None


def _container_host_flag(program: str, args: list[str]) -> str | None:
    """The first docker/podman argument that would let the container reach the host, if any.

    Applies to the container CLI as the command or reached through a runner. Only `run` is allowed: other
    subcommands (exec, cp, compose, ...) act on containers and files outside the server's own.
    """
    in_container_cli = Path(program).name.lower() in _CONTAINER_NAMES
    subcommand_seen = False
    previous: str | None = None
    for token in args:
        if not in_container_cli:
            in_container_cli = Path(token).name.lower() in _CONTAINER_NAMES
            previous = token
            continue
        name = token.split("=", 1)[0]
        if not subcommand_seen and not token.startswith("-"):
            if token != "run":
                return token
            subcommand_seen = True
        elif (
            name in _CONTAINER_HOST_FLAGS
            or "v" in _short_letters(token)
            or name in _CONTAINER_HOST_NAMESPACE_FLAGS
            and token.endswith("=host")
        ):
            return token
        elif token == "host" and previous in _CONTAINER_HOST_NAMESPACE_FLAGS:
            return f"{previous} host"
        previous = token
    return None


def _is_dangerous_env_name(name: str) -> bool:
    upper = name.upper()
    return upper in _DANGEROUS_ENV_NAMES or upper.startswith(_DANGEROUS_ENV_PREFIXES) or upper.endswith(_DANGEROUS_ENV_SUFFIXES)


def validate_stdio_environment(environment: dict[str, str] | None) -> None:
    """Reject environment variables a stdio server may not set (loader, interpreter and search-path variables)."""
    for name in environment or {}:
        if not name or "=" in name or "\0" in name:
            raise ForbiddenError("Environment variable name is invalid", details={"name": name})
        if _is_dangerous_env_name(name):
            raise ForbiddenError(
                f"Environment variable '{name}' is not allowed for stdio servers: it changes what code the process loads",
                details={"name": name},
            )


def sanitize_environment(custom_environment: dict[str, str] | None, inherit_base: bool = True) -> dict[str, str]:
    """Sanitize environment variables passed to child stdio processes.

    Ensures host secrets are not leaked unintentionally to child processes, and drops variables that change
    what code the process loads (a server stored before `validate_stdio_environment` existed may carry them).
    """
    # Start with a safe minimal system environment
    sanitized: dict[str, str] = {}
    if inherit_base:
        safe_keys = {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP"}
        for key in safe_keys:
            if key in os.environ:
                sanitized[key] = os.environ[key]

    if not custom_environment:
        return sanitized

    dropped = []
    for key, value in custom_environment.items():
        if _is_dangerous_env_name(str(key)):
            dropped.append(str(key))
            continue
        sanitized[str(key)] = str(value)
    if dropped:
        logger.warning(f"Not passing environment variable(s) {', '.join(sorted(dropped))} to a stdio server: not allowed")

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

    hostname = _normalize_hostname(parsed.hostname)

    if not allow_private:
        # Check for localhost / loopback
        if hostname in {"localhost", "127.0.0.1", "::1"} or hostname.endswith(".localhost"):
            raise ForbiddenError(
                "Access to localhost/loopback is forbidden in production mode",
                details={"url": url},
            )

        # Check for IP address private ranges & cloud metadata
        ip = _parse_ip_literal(hostname)
        if ip is not None:
            if str(ip) == "169.254.169.254":
                raise ForbiddenError(
                    "Access to cloud instance metadata endpoint is prohibited",
                    details={"url": url},
                )
            if _is_forbidden_ip(ip):
                raise ForbiddenError(
                    f"Access to private/local IP range {ip} is prohibited",
                    details={"url": url, "ip": str(ip)},
                )
        elif hostname.endswith(".local") or hostname.endswith(".internal"):
            # Not a literal IP, it's a domain name
            raise ForbiddenError(
                "Access to internal domain names is prohibited",
                details={"url": url},
            )

    return url.strip()


async def validate_http_url_resolved(url: str, allow_private: bool | None = None) -> str:
    """Validate a remote URL, then check the addresses its hostname resolves to.

    `validate_http_url` only inspects the URL text, so a public name pointing at a private address
    passes it. This resolves the name and rejects the URL if any resolved address is forbidden.

    Limitation: the HTTP client resolves the name again when it connects, so a DNS answer that changes
    between this check and the connection (rebinding) is not caught.
    """
    cleaned = validate_http_url(url, allow_private)
    if allow_private is None:
        allow_private = get_settings().ALLOW_PRIVATE_NETWORK_HTTP
    if allow_private:
        return cleaned

    parsed = urlparse(cleaned)
    hostname = _normalize_hostname(parsed.hostname or "")
    if _parse_ip_literal(hostname) is not None:
        return cleaned  # a literal IP was already checked by validate_http_url

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        async with asyncio.timeout(_DNS_TIMEOUT_SECONDS):
            resolved = await asyncio.get_running_loop().getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (OSError, TimeoutError):
        return cleaned  # unresolvable is not a policy violation; the connection itself will fail

    for *_, sockaddr in resolved:
        ip = ipaddress.ip_address(str(sockaddr[0]).split("%", 1)[0])
        if _is_forbidden_ip(ip):
            raise ForbiddenError(
                f"Host '{hostname}' resolves to private/local address {ip}, which is prohibited",
                details={"url": url, "ip": str(ip)},
            )
    return cleaned


def mask_sensitive_headers(headers: dict[str, str] | None) -> dict[str, str]:
    """Mask values of sensitive headers like Authorization or API keys for safe API responses.

    Besides the well-known names, any header whose name looks like a credential (contains token, key, secret, ...)
    is masked: a downstream server can expect its key under any name.
    """
    if not headers:
        return {}

    masked: dict[str, str] = {}
    for key, value in headers.items():
        name = key.lower()
        if name in SENSITIVE_HEADER_NAMES or any(part in name for part in SENSITIVE_HEADER_NAME_PARTS):
            masked[key] = MASKED_HEADER_VALUE
        else:
            masked[key] = value
    return masked


_NUMERIC_HOST = re.compile(r"^[0-9a-fx.]+$")
_NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")
_DNS_TIMEOUT_SECONDS = 5.0


def _normalize_hostname(hostname: str) -> str:
    """Lower-case, without the trailing dot of a fully qualified name (`localhost.` is `localhost`)."""
    return hostname.lower().rstrip(".")


def _parse_ip_literal(hostname: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """The address a hostname spells literally, or None for a domain name.

    Besides dotted quads and IPv6, this reads the forms the system resolver also accepts as IPv4: shortened
    (`127.1`, `10.1`), hexadecimal (`0x7f.1`, `0x7f000001`), octal (`0177.0.0.1`) and a single number (`2130706433`).
    """
    try:
        return ipaddress.ip_address(hostname)
    except ValueError:
        pass
    if not _NUMERIC_HOST.match(hostname):
        return None
    try:
        return ipaddress.IPv4Address(socket.inet_aton(hostname))
    except OSError:
        return None  # a name made of hex letters, such as cafe.be


def _is_forbidden_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Whether an address is off-limits when private network access is disallowed."""
    if isinstance(ip, ipaddress.IPv6Address):
        # IPv4 carried inside IPv6: mapped (::ffff:a.b.c.d), 6to4 (2002:ab:cd::) and NAT64 (64:ff9b::a.b.c.d)
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif ip.sixtofour is not None:
            ip = ip.sixtofour
        elif ip in _NAT64_PREFIX:
            ip = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified
