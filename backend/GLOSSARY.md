# Domain Glossary

This document defines the canonical domain vocabulary for MCP Hub Backend. All modules, interfaces, tests, and documentation must use these terms consistently.

## Core Concepts

### Server (Downstream MCP Server)
A target external or local Model Context Protocol server connected to the hub via `stdio` (subprocess pipeline) or `streamable-http` (HTTP streaming transport).
- **Registration**: The persistent configuration defining a server's name, transport, environment, and credentials.
- **Health Status**: Operational availability of a downstream server (`UNKNOWN`, `HEALTHY`, `UNHEALTHY`, `DISCONNECTED`).

### Tool (Discovered MCP Tool)
A callable capability discovered dynamically from an active downstream MCP server.
- **Qualified Tool ID**: Unique identifier formatted as `{server_id}:{tool_name}` used in REST routing.
- **Tool Slug**: Namespaced collision-resistant identifier formatted as `{server_slug}__{tool_name}` exposed to upstream agents on `/mcp`.
- **Tool Catalog**: In-memory cache backed by persistent storage indexing all discovered tools across connected servers.

### Execution
A discrete, audited attempt to invoke a resolved Tool on a registered Server, recording input arguments, duration in milliseconds, outcome status, structured output, and correlation metadata.
- An attempt counts as an Execution once its Tool Reference resolves to a Tool, even if it is rejected before reaching the downstream Server (Server disabled, arguments invalid).
- A Tool Reference that resolves to no Tool is not an Execution; it is recorded only as Session activity.
- **Outcome**: every attempt ends in exactly one of:
  - **Succeeded**: the downstream Server ran the Tool and reported success.
  - **Tool Error**: the downstream Server ran the Tool and reported an error.
  - **Failed**: the hub could not complete the call to the downstream Server (transport fault, timeout).
  - **Rejected**: the hub refused the attempt before contacting the downstream Server (unknown Tool, Server disabled, Tool unavailable, arguments invalid).
- **Duration** measures only the downstream call; a Rejected attempt has zero duration.

### Tool Reference
What a caller uses to name the Tool it wants to execute: either a Tool Slug (upstream agents) or a Qualified Tool ID (REST). Resolving a Tool Reference yields exactly one Tool or none.

### Session
A tracked client connection established by an upstream agent (e.g., Claude, Cursor, or MCP SDK client) interacting with the hub.
- Tracks active duration, total tool calls, and execution metrics.

### MCP Gateway (Hub Server)
The hub acting as an upstream MCP Server exposing the aggregated tool catalog over Streamable HTTP at `POST /mcp`.
- Exposes native meta-tools to upstream LLM planners.
- Handles tool list change notifications (`tools/list_changed`) across connected sessions.

### Meta-Tool
Native high-leverage tools provided directly by the MCP Gateway to upstream agents:
- `SEARCH_TOOLS`: Pure keyword and relevance discovery over available downstream tools.
- `MULTI_EXECUTE_TOOLS`: Parallel dispatcher executing multiple independent downstream tool calls concurrently with isolated error handling.

### SessionWorker
The long-running asyncio task dedicated to managing an individual downstream MCP client connection within its own `AsyncExitStack` to guarantee AnyIO cancel scope isolation.
