"""OAuth connections to hosted MCP servers (ADR-0008)."""

# Name the hub registers itself with at each authorization server.
OAUTH_CLIENT_NAME = "MCP Hub"

# How long starting a sign-in waits for the authorization URL (discovery + client registration).
# The console's connect request waits longer: OAUTH_START_TIMEOUT_MS in frontend/src/lib/api/oauth.ts.
OAUTH_START_TIMEOUT_SECONDS = 40.0

# How long the callback waits for the code exchange, the first session and the tool sync.
OAUTH_COMPLETE_TIMEOUT_SECONDS = 60.0

# How long finding a stored server's authorization server metadata may take (servers saved before it was stored).
OAUTH_DISCOVERY_TIMEOUT_SECONDS = 10.0

# `details.reason` of the 502 raised when a server's tokens can no longer be refreshed (health NEEDS_AUTH).
OAUTH_REAUTHORIZATION_REASON = "oauth_reauthorization_required"
