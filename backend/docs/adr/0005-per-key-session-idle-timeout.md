# ADR 0005: Per-API-Key Session Idle Timeout and a Background Job That Completes Idle Sessions

## Status
Accepted. Replaces the fixed 30-minute idle window of ADR-0003 (point 3) with a per-API-key value.

## Date
2026-11-15

## Context
A derived Session (ADR-0003) ended only lazily: when the same client called again after 30 idle minutes, the tracker marked the old Session `completed` and opened a new one. A client that simply stopped calling left its Session `active` for ever, so the Session explorer filled with stale "active" Sessions. The 30 minutes was also the same for every client, although a CI script and an interactive agent pause very differently. Sessions also opened on `tools/list`, so a client that only listed tools left an empty Session behind.

## Decision
1. **The idle timeout is set per API key.** `api_keys.session_idle_minutes` (1-1440, null = the 30-minute default) is chosen when the key is created (`POST /auth/api-keys`) and can be changed later (`PATCH /auth/api-keys/{id}`). It is not the key's expiry: the key keeps working, and only the Session ends.
2. **It is an idle timeout.** A Session is completed after that many minutes with no tool call; an agent that keeps working keeps one Session.
3. **Each Session snapshots its timeout when it opens** (`mcp_sessions.idle_timeout_seconds`), so changing the key's value applies to Sessions opened afterwards, and an open Session is never cut short. Rows from before this decision have none and use the default.
4. **A Session opens on the first tool call** (`SEARCH_TOOLS` or `MULTI_EXECUTE_TOOLS`). `tools/list` is not attributed to a Session.
5. **A background job completes idle Sessions.** An APScheduler `AsyncIOScheduler`, started and shut down in the FastAPI lifespan, runs the cron job `SESSION_SWEEP_JOB_ID` on `SESSION_SWEEP_CRON` (every minute by default) (`max_instances=1`, `coalesce=True`). It runs a single `UPDATE` that marks `completed` every `active` Session whose `last_activity_at` plus its own timeout (or the default) has passed. It leaves `last_activity_at` unchanged, so the explorer still says when the agent last acted. The statement is idempotent, so every hub instance can run the job with no lock or leader election. Code: `app/background_service/session_sweeper.py`, `app/background_service/scheduler.py`; idle-timeout constants in `app/core/constants/session_constants.py`, job id, cron and misfire grace in settings (`SESSION_SWEEP_*`); shared idle arithmetic in `app/helpers/session_idle.py`.

## Why
- **Not FastAPI `BackgroundTasks`:** it runs once, after a response, inside a request. It would never fire for a client that has gone silent, which is exactly the Session this job exists to close.
- **APScheduler over a hand-written loop:** cron triggers, misfire handling and overlap protection come built in, and more jobs can be added to `app/background_service/` the same way.
- **Not Celery beat or arq:** they need a separate worker and a broker (Redis) for one small idempotent statement.
- **Snapshot on the Session rather than reading the key on every check:** it makes "a change applies to later Sessions" true by construction, lets the sweep be one statement with no join, and keeps working if the key is revoked or deleted.

## Consequences
- The explorer shows Sessions as `completed` within about a minute of their idle timeout passing, whether or not the client comes back.
- A client that only lists tools no longer appears in the Session explorer.
- The job's schedule and the default timeout are code constants, not `.env` settings.
- Running several instances runs the job several times a minute; each run after the first finds nothing to do.
