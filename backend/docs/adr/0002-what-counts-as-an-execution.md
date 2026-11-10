# ADR 0002: What Counts as an Execution

## Status
Accepted

## Date
2026-11-10

## Decision
An attempt becomes an Execution, and is persisted as an execution row, only once its Tool Reference resolves to a Tool on a registered Server. An attempt rejected *after* resolution (Server disabled, Tool unavailable, arguments invalid) is persisted with the status `rejected` and zero duration, which keeps it distinct from `failed` (the downstream Server ran the call and it went wrong). A Tool Reference that resolves to no Tool produces **no** execution row: it updates the Session's last activity and emits a structured warning log, nothing more.

## Why
Before this decision, rejected attempts left no trace, so the agent mistakes the Session explorer is meant to surface (bad arguments, calls to disabled Servers) were invisible. Recording them as `rejected` closes that gap. Folding them into `failed` would mix up "the agent asked wrongly" with "the tool broke".

Unknown Tool References are excluded on purpose. Every Execution keeps a non-null Server and Tool, which matches the glossary ("an attempt to invoke a resolved Tool") and the existing schema, where `tool_executions.server_id` is NOT NULL.

## Considered Options
- **Record every attempt, including unknown Tool References.** Rejected because it needs a nullable `server_id`, which breaks the invariant that every Execution has a Server and Tool and forces every reader of executions to handle a missing Server. An unknown reference is a Session-level event. If it needs to be tracked, the place is a Session event (see the Session tracker candidate), not a Server-less Execution.
- **Record only attempts that reach the downstream Server (previous behaviour).** Rejected because it hides the most common agent errors.

## Consequences
- `ToolCallStatus` gains `rejected`. The frontend's `ToolCallStatus` type, the Session filter and the status badges must handle it.
- Execution counts and failure rates now include rejected attempts, so dashboards that equate "not completed" with "failed" have to tell them apart.
