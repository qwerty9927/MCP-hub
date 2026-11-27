# Backend pending: UI waiting on the API

The console redesign keeps every designed element in place. Where the backend can't serve the data yet, the element shows a **Backend pending** badge whose tooltip names what it waits for. This page is the handoff for the API team.

- Source of truth: `src/lib/backend-pending.ts` (`BACKEND_PENDING`). The badge and this table use the same ids; `src/test/pending-backend.test.tsx` fails if an id is missing here.
- When an endpoint ships: wire the UI to it, delete the entry and its badge, and delete the row below.

## Checklist

Picked to implement next (tick when the endpoint ships and the badge is gone):

- [x] **Trend chart + delta** · `GET /executions/timeseries`, `previous_total_calls` on tool-usage
- [x] **Last-hour range** · `range=1h` on tool-usage and timeseries
- [x] **P90 latency** · `p90_duration_ms` overall and per tool on tool-usage
- [x] **Server filter on usage** · `server_id` on tool-usage and timeseries
- [ ] **Auto-enable read-only tools** (`auto-enable-readonly`) · M · store tool annotations, user settings store
- [ ] **Display name + verified email** (`profile-display-name`, `profile-verified`) · M · `display_name`, `PATCH /auth/me`, verification flow (needs email sending)
- [ ] **Active sessions** (`settings-sessions`) · S · list and revoke console sign-ins
- [ ] **Tool policies** (`settings-tool-policies`) · M · allow / block / require-review rules checked before a call

Not picked yet:

- [ ] Tool review queue (`new-tools-review`) · L
- [ ] Rate limits (`server-rate-limit`, `settings-rate-limits`) · L
- [ ] Remote MCP catalog (`remote-catalog`) · M
- [ ] Delete profile (`profile-delete`) · S
- [ ] Notifications (`settings-notifications`) · L
- [ ] Audit logs + webhooks (`settings-audit-logs`, `settings-webhooks`) · M–L
- [ ] Members and roles (`settings-members`) · XL
- [ ] Hub switcher (`hub-switcher`) · XL

## Tools and servers

| Id | What the user would get | Backend needs | Where | Today |
|---|---|---|---|---|
| `new-tools-review` | Review newly discovered tools before agents can call them | stable tool ids across refresh (today `replace_server_tools` deletes and re-inserts), `first_seen_at`, a review status on tools, an approve endpoint | Overview callout, Server callout | Callout explains tools go live at once |
| `server-rate-limit` | "Calls today / limit" per server | per-server rate limit config and usage, e.g. `GET /servers/{id}/quota` | Server › Usage by tool | Calls in the chosen range |
| `remote-catalog` | Remote MCP catalogs (e.g. Cloudflare) in Discovery | a catalog of remote MCP servers beyond the static `oauth_providers.json` | Discovery | OAuth providers from `GET /oauth/providers` |

## Hub and account

| Id | What the user would get | Backend needs | Where | Today |
|---|---|---|---|---|
| `hub-switcher` | Switch between hub instances | workspaces / hub instances model and a list endpoint | Sidebar | Shows the current backend's host |
| `profile-display-name` | Display name | `display_name` on users, `PATCH /auth/me` | Settings › General | Disabled button |
| `profile-verified` | Verified email badge | `email_verified` on `GET /auth/me` and a verification flow | Settings › General | Email only |
| `profile-delete` | Delete profile | `DELETE /auth/me` | Settings › General | Disabled button |
| `auto-enable-readonly` | Auto-enable read-only tools | tool annotations (`readOnlyHint`, `destructiveHint`) stored on tools, and a server-side user settings store | Settings › General | Disabled switch |

## Settings sections (placeholder pages)

| Id | Section | Backend needs |
|---|---|---|
| `settings-notifications` | User › Notifications | notification preferences and delivery, e.g. `GET/PUT /settings/notifications` |
| `settings-sessions` | User › Active Sessions | list and revoke console sign-ins (refresh-token families), e.g. `GET /auth/sessions` |
| `settings-members` | Hub › Members | members and roles on a shared hub |
| `settings-tool-policies` | Hub › Tool Policies | hub-wide allow/deny and approval policies for tools |
| `settings-rate-limits` | Hub › Rate Limits | configurable per-server / per-key rate limits |
| `settings-audit-logs` | Hub › Audit Logs | an audit log table and `GET /audit-logs` |
| `settings-webhooks` | Hub › Webhooks | webhook subscriptions and delivery |

## Served today without backend changes

- **Recents**: recorded per browser in `localStorage` (`mcp-hub:recents`).
- **Timezone and keyboard shortcuts**: per-browser preferences (`mcp-hub:preferences`).
- **Quick search (⌘K)**: fans out to `GET /servers?search=`, `GET /tools?search=` and `GET /executions?tool_name=`. A single search endpoint would be faster but isn't required.
