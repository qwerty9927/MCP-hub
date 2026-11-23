"""Constants for console sign-in: the refresh token cookie and its purge job (ADR-0009)."""

# The httpOnly cookie carrying the console refresh token. Scoped to the /auth routes (path set from API_V1_STR).
REFRESH_COOKIE_NAME: str = "mcp_hub_refresh"
REFRESH_COOKIE_PATH_SUFFIX: str = "/auth"

# /auth/refresh and /auth/logout read the cookie, so they also require this header. A cross-site page cannot send
# a custom header without a CORS preflight, which CORS_ORIGINS refuses: this is the CSRF check.
CONSOLE_CLIENT_HEADER: str = "X-MCP-Hub-Client"
CONSOLE_CLIENT_HEADER_VALUE: str = "console"

# Refresh tokens are prefixed so a leaked one is recognisable, like API keys (`mhk_`).
REFRESH_TOKEN_PREFIX: str = "mhr_"

# The APScheduler job that deletes expired refresh tokens, and how often it runs.
REFRESH_TOKEN_PURGE_JOB_ID: str = "purge-expired-refresh-tokens"
REFRESH_TOKEN_PURGE_INTERVAL_MINUTES: int = 60
REFRESH_TOKEN_PURGE_MISFIRE_GRACE_SECONDS: int = 300
