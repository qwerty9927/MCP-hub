# ADR 0003: Session Identity Without Transport Sessions

## Status
Accepted. Point 2 (transport sessions) superseded by ADR-0004: `/mcp` is stateless and every Session is derived. The fixed 30-minute idle window of point 3 is replaced by a per-API-key timeout, enforced by a background job (ADR-0005).

## Date
2026-11-12

## Context
Until MCP protocol 2025-11-25, a client opened a Streamable HTTP session with `initialize`, the server answered with an `Mcp-Session-Id`, and every later request carried it. The hub used that ID as its Session, so the Session explorer could group an agent's tool calls.

Protocol 2026-07-28 (served by `mcp` 2.3) removed the handshake: each POST to `/mcp` is a self-contained request, with the client's name and version in its `_meta` and no session ID. For those clients the hub had nothing to key a Session on. Executions were stored with no Session, the explorer showed nothing, and the per-request SDK session objects were added to the notification set and never removed.

## Decision
The hub supplies its own session identity, from things it can trust:

1. **Every `/mcp` request is authenticated** (ADR context: accounts and API keys). An MCP client presents an API key in the `x-api-key` header. No valid key, 401. (Amended: console login tokens were originally accepted too; `/mcp` is now API-key only.)
2. **Handshake-era clients** keep using the transport session ID. The Session is stamped with the account and API key, and the SDK binds the transport session to the credential that opened it, so another key cannot use it.
3. **Sessionless clients** get a **derived Session**, keyed on a fingerprint of `(account, API key, client name, client version)`. Requests with the same fingerprint join the most recent active Session with it, until that Session has been idle for 30 minutes (the SDK's own idle timeout). After that it is marked `completed` and the next request opens a new one.
4. Session metadata records `session_source`: `transport` or `derived`.
5. No SDK sessions are kept for notifications: the hub's tool list is fixed, so it sends no `tools/list_changed`.

## Why
- Account + API key is the only identity the hub can verify. The client name, version and source address are client-supplied or shared (NAT, proxies), so on their own they would merge unrelated clients, and nothing would stop one caller writing into another's Session.
- One API key per client is what lets two identical clients (same name, version, network) be told apart. This is the recommended set-up, and the console says so when a key is created.
- An idle window approximates "one working session" for clients that never say when they start or stop.

## Considered Options
- **Derive from client name/version + caller IP, no accounts.** Rejected: unauthenticated, merges clients behind one address, and spoofable.
- **A custom `X-Hub-Session-Id` header.** Rejected as the primary key: it needs every client configured, and is still unauthenticated. Can be added later on top of this design.
- **Split by TCP connection.** Rejected: HTTP clients reuse and drop connections freely, so one agent would scatter over many Sessions.

## Consequences
- Two clients that share one API key and identify identically are grouped into one Session.
- A long-running agent that pauses for more than 30 minutes continues in a new Session.
- `mcp_sessions` gains `user_id` (originally `owner_id`, renamed and made NOT NULL later), `api_key_id` and `client_fingerprint`; the lookup is indexed on `(user_id, client_fingerprint, last_activity_at)`.
