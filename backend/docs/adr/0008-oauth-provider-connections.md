# ADR 0008: Connecting Hosted MCP Servers with OAuth

## Status
Accepted.

## Date
2026-11-17

## Context
Many MCP servers are hosted streamable-HTTP endpoints that require OAuth (Linear, Notion, Sentry, Atlassian…). Before this change an owner could only register them by pasting a bearer token into `http_config.headers`, which expires and cannot be refreshed. The console now offers a provider picker: choose a provider, sign in, and get a working Server. The manual form stays for everything else.

## Decision
1. **A curated catalog.** `app/infrastructure/oauth/oauth_providers.json` lists the providers the console offers (id, name, description, category, MCP URL). A provider without dynamic client registration is marked `requires_client`; it can be connected only once an admin puts an OAuth app's credentials in `OAUTH_CLIENTS` under its id. Until then the console shows it as "Needs setup".
2. **The MCP SDK does the OAuth.** Discovery (RFC 9728 / RFC 8414), dynamic client registration (RFC 7591), PKCE, the RFC 8707 resource parameter, issuer checks and refresh all come from `mcp.client.auth.OAuthClientProvider`. The hub supplies only where credentials live and, during a sign-in, the redirect and callback handlers.
3. **A sign-in is a background task.** `POST /oauth/connect` starts a task that opens an MCP session through the SDK provider, inside an ephemeral `SessionWorker` (`ConnectionManager.authorize`), as every downstream connection is. When the server answers 401, the SDK calls our redirect handler with the authorization URL, which the endpoint returns. The task then waits in our callback handler until the authorization server sends the browser to `GET /oauth/callback`, which hands over the code. The SDK exchanges it, the session initializes, and only then is the Server created (`auth_type = oauth`, `oauth_provider_id`) with its credentials, connected and its Tools synced. The callback redirects the browser to the console's `/oauth/complete` with the result.
4. **Pending sign-ins live in memory** (`OAuthFlowRegistry`), keyed by the OAuth `state`, like the live downstream sessions in `ConnectionManager`. A state is single-use and expires after `OAUTH_FLOW_TIMEOUT_SECONDS`.
5. **Credentials are encrypted at rest.** `server_oauth_credentials` holds the client registration and tokens as Fernet ciphertext under `OAUTH_ENCRYPTION_KEY`, plus the access token's absolute expiry and the owner's `user_id` (a copy of the server's, so every lookup is scoped to the owner). They are never returned by the API. Deleting the Server deletes them (cascade).
6. **Refresh is silent; re-authorization is explicit.** On connect, `ConnectionManager` builds the SDK provider over the stored credentials with no redirect handler. An expired access token is refreshed before use and the new one is written back. If the tokens cannot be refreshed, the connect fails with a `BadGatewayError` (502) whose `details.reason` is `OAUTH_REAUTHORIZATION_REASON` (`oauth_reauthorization_required`), `ServerRegistryService.record_connect_failure` sets the Server's health to `NEEDS_AUTH`, and the owner signs in again with `POST /servers/{id}/oauth/reconnect`. Reconnecting reuses the stored client registration.

## Why
- **The SDK over our own flow:** the spec has many details (fallback discovery URLs, issuer binding, step-up scopes); the SDK tracks them, so the hub follows spec changes with an SDK upgrade.
- **Create the Server only after sign-in:** an abandoned or denied sign-in leaves nothing behind.
- **In-memory pending state:** the hub already keeps live sessions per process, and a pending sign-in is short-lived; a table would add a cleanup job for no gain at this scale.
- **Absolute expiry:** the SDK reads a relative `expires_in`, and a token loaded after a restart would otherwise look valid until a 401 sent it down the full sign-in path. `HubOAuthClientProvider` restores the remaining lifetime on load.

## Consequences
- More than one API process needs sticky routing for `/oauth/callback`, or the registry must move to shared storage.
- Losing or rotating `OAUTH_ENCRYPTION_KEY` makes every stored credential unreadable; those Servers must be reconnected.
- `ServerHealthStatus` gains `NEEDS_AUTH`; `ServerResponse` gains `auth_type` and `oauth_provider_id`.
- New settings: `OAUTH_ENCRYPTION_KEY`, `PUBLIC_API_BASE_URL`, `FRONTEND_BASE_URL`, `OAUTH_CLIENTS`, `OAUTH_FLOW_TIMEOUT_SECONDS`.
- Catalog URLs must be checked against each provider's documentation when the catalog changes.

Code: `app/services/oauth_service.py`, `app/infrastructure/oauth/`, `app/infrastructure/repositories/oauth_credential_repository.py`, `app/api/v1/oauth_router.py`, `SessionWorker._oauth_auth`. Tests: `tests/integration/test_oauth_flow.py` against `tests/fake_oauth_server.py`, a real OAuth-protected MCP server built from the SDK's auth server.
