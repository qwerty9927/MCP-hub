# ADR 0004: Stateless `/mcp` Endpoint

## Status
Accepted. Supersedes point 2 of ADR-0003 (transport sessions for handshake-era clients).

## Date
2026-11-15

## Context
`/mcp` ran the MCP SDK's stateful Streamable HTTP manager. A handshake-era client opened a transport session with `initialize`, received an `Mcp-Session-Id`, and had to send it on every later request. Those sessions lived only in the hub process's memory, so:

- a backend restart, or 30 idle minutes, made every open client fail with `404 Session not found` until it re-initialized, which many clients do not do on their own;
- requests had to reach the instance that held the session, so the hub could not run behind a load balancer without sticky routing;
- the hub kept two ways of identifying a Session (transport and derived, ADR-0003).

The hub uses none of what a transport session is for. It sends no server-initiated requests (sampling, elicitation, roots), no `tools/list_changed` (its tool list is fixed), and no progress or log notifications.

## Decision
1. `/mcp` runs the SDK in stateless mode with JSON responses (`stateless_http=True`, `json_response=True`). Every POST gets its own short-lived transport. The hub issues no `Mcp-Session-Id` and ignores one a client sends. `GET` and `DELETE` answer `405`. `initialize` is still answered, for clients that send it.
2. Every Session is a derived Session (ADR-0003, point 3). The hub never takes a Session ID from the client.
3. A stateless server forgets `initialize`, so a handshake-era client's later requests carry no client name. For such requests the client is identified by its `User-Agent`. Clients that name themselves (2026-07-28 `_meta`) are keyed on name + version as before.

## Consequences
- No more `404 Session not found`: restarts and idle time are invisible to clients, and any instance can answer any request.
- What the LLM sees does not change: the same two meta-tools, schemas and results.
- Server-to-client features cannot be added on `/mcp` without revisiting this decision (sampling, elicitation, a notification stream). Notifications inside a single response would still work.
- A request cut off mid-call cannot be resumed (it could not before either: there was no event store). A client retry may run tools again.
- Handshake-era clients sharing one API key and one User-Agent are grouped into one Session. One API key per client keeps them apart.
- Session rows from before this decision may still say `session_source: transport`; they stay readable.
