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
A discrete, audited invocation of an MCP tool, recording input arguments, duration in milliseconds, success/failure status, structured output, and correlation metadata.

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
