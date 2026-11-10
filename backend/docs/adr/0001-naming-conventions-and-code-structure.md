# ADR 0001: Explicit Suffix Conventions and Schema Standardization

## Status
Accepted

## Date
2026-11-10

## Context
Prior to this decision, the codebase exhibited divergent naming conventions across architectural layers:
- API routers were suffixed with `_route.py` (`servers_route.py`).
- Repositories were abbreviated with `_repo.py` (`server_repo.py`).
- Models used `_model.py` (`server_model.py`), entities used `_entity.py` (`server_entity.py`), and enums used `_enum.py` (`server_enum.py`).
- Schemas lacked suffixes entirely (`server.py`, `tool.py`, `common.py`), creating ambiguity when importing symbols.
- Schemas mixed naming paradigms: `ServerResponse` vs `ConnectionConfigRead`, `ToolResponse` vs `ToolRead`.
- A legacy deprecated module (`app/services/mcp_gateway.py`) remained in production paths, emitting runtime warnings.

This caused navigational friction, cognitive load, and occasional import confusion for both developers and AI coding agents.

## Decision
We standardize on explicit, full-word role suffixes for structural modules and uniform request/response naming for schemas:

1. **File Suffix Standard**:
   - Routers: `app/api/v1/*_router.py` (e.g., `servers_router.py`, `tools_router.py`, `executions_router.py`, `sessions_router.py`, `system_router.py`)
   - Schemas: `app/schemas/*_schema.py` (e.g., `server_schema.py`, `tool_schema.py`, `execution_schema.py`, `session_schema.py`, `connection_schema.py`, `system_schema.py`, `common_schema.py`)
   - Repositories: `app/infrastructure/repositories/*_repository.py` (e.g., `server_repository.py`, `tool_repository.py`, `execution_repository.py`, `session_repository.py`)
   - Models: `app/models/*_model.py` (e.g., `server_model.py`, `tool_model.py`, `execution_model.py`, `session_model.py`, `base_model.py`)
   - Domain Entities: `app/domain/*_entity.py` (e.g., `server_entity.py`, `tool_entity.py`, `execution_entity.py`, `session_entity.py`)
   - Enums: `app/core/enums/*_enum.py` (e.g., `server_enum.py`, `session_enum.py`)
   - Services: Descriptive noun phrases without suffix in `app/services/` (e.g., `server_registry.py`, `connection_manager.py`, `tool_catalog.py`, `tool_executor.py`, `session_explorer.py`)

2. **Schema Suffix Standard**:
   - Inbound request payloads strictly use `*Request` (e.g., `ServerCreateRequest`, `ServerUpdateRequest`, `SessionCreateRequest`, `ToolExecuteRequest`).
   - Outbound response payloads strictly use `*Response` (e.g., `ServerResponse`, `ServerTestResponse`, `ToolResponse`, `ToolSummaryResponse`, `ToolExecuteResponse`, `ExecutionResponse`, `SessionResponse`, `SessionDetailResponse`, `ToolCallResponse`, `ConnectionConfigResponse`).
   - Backward-compatible type aliases (e.g., `ServerCreate = ServerCreateRequest`) may be retained temporarily to prevent breaking external consumers.

3. **Deletion of Deprecated Modules**:
   - `app/services/mcp_gateway.py` is deleted per the deletion test. Callers import from `app.mcp.mcp_server`.

## Consequences
- **Positive**:
  - Predictable, symmetric file names across all layers.
  - Zero ambiguity when importing schemas vs models vs routers.
  - Pydantic schema naming aligns with the API contract (`Request` for inputs, `Response` for outputs).
  - Eliminates runtime deprecation warnings and dead code stubs.
- **Negative / Neutral**:
  - File moves require updating imports across `app/`, `tests/`, and `AGENT.md`.
