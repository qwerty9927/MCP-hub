# Backend pending: UI waiting on the API

The console redesign keeps every designed element in place. Where the backend can't serve the data yet, the element shows a **Backend pending** badge whose tooltip names what it waits for. This page is the handoff for the API team.

- Source of truth: `src/lib/backend-pending.ts` (`BACKEND_PENDING`). The badge and this table use the same ids; `src/test/pending-backend.test.tsx` fails if an id is missing here.
- When an endpoint ships: wire the UI to it, delete the entry and its badge, and delete the row below.

## Checklist

Done:

- [x] **Trend chart + delta** · `GET /executions/timeseries`, `previous_total_calls` on tool-usage
- [x] **Last-hour range** · `range=1h` on tool-usage and timeseries
- [x] **P90 latency** · `p90_duration_ms` overall and per tool on tool-usage
- [x] **Server filter on usage** · `server_id` on tool-usage and timeseries

Next:

- [ ] **Auto-enable read-only tools** (`auto-enable-readonly`) · M · store tool annotations, user settings store
- [ ] **Display name + verified email** (`profile-display-name`, `profile-verified`) · M · `display_name`, `PATCH /auth/me`, verification flow (needs email sending)
- [ ] **Active sessions** (`settings-sessions`) · S · list and revoke console sign-ins
- [ ] **Tool policies** (`settings-tool-policies`) · M · allow / block / require-review rules checked before a call

## Pending items

| Id | What the user would get | Backend needs | Where | Today |
|---|---|---|---|---|
| `profile-display-name` | Display name | `display_name` on users, `PATCH /auth/me` | Settings › General | Disabled button |
| `profile-verified` | Verified email badge | `email_verified` on `GET /auth/me` and a verification flow | Settings › General | Email only |
| `auto-enable-readonly` | Auto-enable read-only tools | tool annotations (`readOnlyHint`, `destructiveHint`) stored on tools, and a server-side user settings store | Settings › General | Disabled switch |
| `settings-sessions` | List and revoke your console sign-ins | refresh-token families exposed, e.g. `GET /auth/sessions` and a revoke endpoint | Settings › Active Sessions | Placeholder page |
| `settings-tool-policies` | Hub-wide allow, block or require-review rules for tools | policy storage and a check in the executor before a call | Settings › Tool Policies | Placeholder page |

## Dropped from the design

Removed from the console on 2026-11-28 and not planned: hub switcher (workspaces), members and roles, audit logs and webhooks, notifications, rate limits (per server and per key), delete profile, remote MCP catalog (e.g. Cloudflare's) in Discovery, and the tool review queue. Bring one back by adding its id to `BACKEND_PENDING`, its UI, and a row here.

## Served today without backend changes

- **Recents**: recorded per browser in `localStorage` (`mcp-hub:recents`).
- **Timezone and keyboard shortcuts**: per-browser preferences (`mcp-hub:preferences`).
- **Quick search (⌘K)**: fans out to `GET /servers?search=`, `GET /tools?search=` and `GET /executions?tool_name=`. A single search endpoint would be faster but isn't required.
