# ADR 0007: Per-API-Key Tool Visibility

## Status
Accepted.

## Date
2026-11-16

## Context
Every API key saw every Tool of its Account's enabled Servers: `SEARCH_TOOLS` returned them all and `MULTI_EXECUTE_TOOLS` could run any of them. Owners want to give each client only the Tools it needs, for example a CI key that sees only a server's read tools while an agent key sees everything.

## Decision
1. **Visibility belongs to the API key.** The owner picks a key and shows or hides each of a Server's Tools for it. There is no global per-Tool switch.
2. **Every key sees every Tool by default.** Only the exceptions are stored: a row in `api_key_disabled_tools (api_key_id, server_id, tool_name)` means the key cannot see or run that Tool. Existing keys, new keys and newly discovered Tools are visible until hidden.
3. **Keyed by Server and Tool name, not Tool ID.** A Server's Tools get new IDs on every re-discovery, so an ID-keyed setting would be lost on reconnect. A name-keyed one survives it and applies again if a Tool disappears and returns. Deleting the key or the Server deletes its rows (cascade).
4. **Hidden means hidden and blocked.** `SEARCH_TOOLS` with the key leaves the Tool out (a `NOT EXISTS` in the same pgvector query, ADR-0006). Running it with the key is a Rejected Execution with reason `tool_disabled` (ADR-0002): the Tool resolved, so the attempt is recorded and the owner sees it in the Session explorer.
5. **Only API-key calls are limited.** The console signs in with a login token, so its tool lists, search and the REST execute route are not filtered by any key.

API: `GET /auth/api-keys/{api_key_id}/servers/{server_id}/tools` lists a Server's Tools with `enabled` for the key; `PATCH .../tools/{tool_name}` with `{"enabled": bool}` changes one. Both are owner-scoped (404 otherwise). Code: `app/services/tool_access_service.py`, `app/infrastructure/repositories/tool_access_repository.py`, `ToolExecutor._rejection_for`, `PostgresToolRepository.search_by_embedding`.

## Why
- **Deny-list over allow-list:** existing keys keep working with no setup, and a newly added Tool is usable at once. Owners who want an allow-list hide what a key should not have.
- **Per key, not per Tool:** the question owners ask is "what may this client do", and one key per client is already the recommended set-up (ADR-0003).
- **Reject rather than "unknown tool" on execution:** an unknown-tool outcome is not recorded, so the owner could not see that a client tried a hidden Tool.

## Consequences
- A Tool hidden from a key and later renamed on its Server becomes visible again under the new name.
- Hiding a Tool from every key means hiding it once per key.
- `RejectionReason` gains `tool_disabled`; the REST execute route maps it to 403 for any future caller that passes a key.
