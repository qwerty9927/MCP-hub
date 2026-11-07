# MCP Hub REST API Specification & Integration Contract

**Version:** 1.0.0  
**Base URL:** `/api/v1`  
**Protocol:** REST / JSON  
**OpenAPI Specification:** Available at `/openapi.json` and interactive Swagger docs at `/docs`.

This document forms the binding interface contract between the MCP Hub Backend and external clients, including the decoupled React frontend.

---

## 1. General Architecture & Design Conventions

### 1.1 HTTP Status Codes

| Code | Meaning | Use Case |
| :--- | :--- | :--- |
| `200 OK` | Success | Successful GET, PATCH, execution, or action response. |
| `201 Created` | Created | Successfully registered a new MCP server. |
| `204 No Content` | No Content | Successful deletion of an entity. |
| `400 Bad Request` | Client Error | Attempting operations on disabled servers or invalid states. |
| `403 Forbidden` | Security Violation | Disallowed executable, command injection, or SSRF attempt. |
| `404 Not Found` | Not Found | Target server, tool, or execution record not found. |
| `409 Conflict` | Conflict | Server with duplicate name already registered. |
| `422 Unprocessable`| Validation Error | Payload structure or JSON schema validation failure. |
| `502 Bad Gateway` | Upstream Failure | MCP Server process failure or upstream connectivity breakdown. |
| `504 Gateway Timeout`| Timeout | MCP client initialization or tool execution exceeded timeout. |
| `500 Server Error` | Internal Error | Unhandled backend exception (sanitized). |

### 1.2 Correlation ID Tracking
Every request can supply an `X-Correlation-ID` header. If absent, the backend assigns a UUID. The response will always echo the `X-Correlation-ID` header for distributed tracing and client log correlation.

### 1.3 Standard Error Format
All errors adhere to this consistent envelope:
```json
{
  "error": {
    "code": "404",
    "message": "Server with id '54c5dce7-c9af-40c6-b822-450131216549' not found",
    "details": {
      "server_id": "54c5dce7-c9af-40c6-b822-450131216549"
    }
  }
}
```

### 1.4 Standard Pagination Envelope
All listing endpoints return records wrapped in this envelope:
```json
{
  "items": [],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

---

## 2. Server Management Endpoints

### 2.1 Register MCP Server
`POST /api/v1/servers`

Registers a new MCP server. Validates command against the security allowlist or checks URL for SSRF protection.

#### Request Body (`stdio` Transport):
```json
{
  "name": "local-math-tools",
  "description": "Safe math expression evaluation tools",
  "transport": "stdio",
  "stdio_config": {
    "command": "python3",
    "args": ["-m", "demo_server.server"],
    "env": {
      "CALC_PRECISION": "4"
    }
  },
  "enabled": true
}
```

#### Request Body (`streamable-http` Transport):
```json
{
  "name": "remote-data-tools",
  "description": "Remote Streamable HTTP MCP Server",
  "transport": "streamable-http",
  "http_config": {
    "url": "https://mcp.internal.example.com/mcp",
    "headers": {
      "Authorization": "Bearer s3cr3t-t0k3n"
    }
  },
  "enabled": true
}
```

#### Response (`201 Created`):
> **Note:** Sensitive headers (e.g., `Authorization`) are automatically masked (`********`) to prevent credential leakage.
```json
{
  "id": "e427b3b6-733d-4c3e-862d-96116ca31614",
  "name": "local-math-tools",
  "description": "Safe math expression evaluation tools",
  "transport": "stdio",
  "connection_config": {
    "command": "python3",
    "args": ["-m", "demo_server.server"],
    "url": null,
    "headers": null
  },
  "enabled": true,
  "health_status": "UNKNOWN",
  "last_connected_at": null,
  "last_health_check_at": null,
  "discovered_tool_count": 0,
  "created_at": "2026-10-24T15:00:00Z",
  "updated_at": "2026-10-24T15:00:00Z"
}
```

---

### 2.2 List Registered Servers
`GET /api/v1/servers`

#### Query Parameters:
- `page` *(int, default: 1)*: Page number.
- `page_size` *(int, default: 20, max: 100)*: Items per page.
- `enabled` *(bool, optional)*: Filter by `true` or `false`.
- `transport` *(string, optional)*: `stdio` or `streamable-http`.
- `health_status` *(string, optional)*: `UNKNOWN`, `HEALTHY`, `UNHEALTHY`, `CONNECTING`, `DISCONNECTED`.
- `search` *(string, optional)*: Substring match against `name` or `description`.
- `sort_by` *(string, default: "created_at")*: `created_at`, `name`, `updated_at`, `discovered_tool_count`.
- `sort_order` *(string, default: "desc")*: `asc` or `desc`.

#### Response (`200 OK`):
```json
{
  "items": [
    {
      "id": "e427b3b6-733d-4c3e-862d-96116ca31614",
      "name": "local-math-tools",
      "description": "Safe math expression evaluation tools",
      "transport": "stdio",
      "connection_config": {
        "command": "python3",
        "args": ["-m", "demo_server.server"],
        "url": null,
        "headers": null
      },
      "enabled": true,
      "health_status": "HEALTHY",
      "last_connected_at": "2026-10-24T15:02:11Z",
      "last_health_check_at": "2026-10-24T15:02:11Z",
      "discovered_tool_count": 3,
      "created_at": "2026-10-24T15:00:00Z",
      "updated_at": "2026-10-24T15:02:11Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

### 2.3 Get Server by ID
`GET /api/v1/servers/{server_id}`

#### Response (`200 OK`):
Returns the single `ServerRead` object matching the UUID.

---

### 2.4 Update Server
`PATCH /api/v1/servers/{server_id}`

Supports partial updates to name, description, transport parameters, or enabled flag.

#### Request Body:
```json
{
  "description": "Updated math server description",
  "enabled": false
}
```

---

### 2.5 Delete Server
`DELETE /api/v1/servers/{server_id}`

Terminates active sessions, deletes server configuration, and purges tools from the catalog.

#### Response:
`204 No Content`

---

### 2.6 Connect to Server
`POST /api/v1/servers/{server_id}/connect`

Initializes the MCP client session, performs protocol handshake, discovers tools, and sets health status to `HEALTHY`.

#### Response (`200 OK`):
Returns updated `ServerRead` object with `health_status: "HEALTHY"`.

---

### 2.7 Disconnect from Server
`POST /api/v1/servers/{server_id}/disconnect`

Gracefully closes active client session and releases subprocess or HTTP stream resources.

#### Response (`200 OK`):
Returns updated `ServerRead` object with `health_status: "DISCONNECTED"`.

---

### 2.8 Test Server Connection
`POST /api/v1/servers/{server_id}/test-connection`

Performs an ephemeral test connection and tool discovery to verify connectivity without leaving a persistent connection open.

#### Response (`200 OK`):
```json
{
  "success": true,
  "message": "Successfully connected to 'local-math-tools'. Discovered 3 tools.",
  "tools_count": 3,
  "latency_ms": 42.15
}
```

---

### 2.9 Refresh Server Tools
`POST /api/v1/servers/{server_id}/refresh-tools`

Refreshes discovered tools from the server and updates catalog cache.

#### Response (`200 OK`):
Returns array of `ToolRead` items.

---

## 3. Tool Discovery & Execution Endpoints

### 3.1 Unified Tool Catalog
`GET /api/v1/tools`

Aggregates discovered tools across all enabled MCP servers. Handles duplicate tool names using server-qualified IDs (`{server_id}:{tool_name}`).

#### Query Parameters:
- `page` *(int, default: 1)*
- `page_size` *(int, default: 20)*
- `server_id` *(UUID, optional)*: Filter to a single server.
- `tool_name` *(string, optional)*: Filter by tool name.
- `status` *(string, optional)*: `AVAILABLE`, `UNAVAILABLE`.
- `search` *(string, optional)*: Search in tool name, description, or server name.

#### Response (`200 OK`):
```json
{
  "items": [
    {
      "id": "e427b3b6-733d-4c3e-862d-96116ca31614:calculate",
      "name": "calculate",
      "description": "Safely calculate a mathematical expression (e.g., '12 + 4 * 2')",
      "input_schema": {
        "type": "object",
        "properties": {
          "expression": {
            "type": "string",
            "description": "Expression string to calculate"
          }
        },
        "required": ["expression"]
      },
      "server_id": "e427b3b6-733d-4c3e-862d-96116ca31614",
      "server_name": "local-math-tools",
      "availability_status": "AVAILABLE",
      "last_discovered_at": "2026-10-24T15:02:11Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

### 3.2 Get Server-Specific Tools
`GET /api/v1/servers/{server_id}/tools`

Returns tools discovered strictly for the specified server.

---

### 3.3 Get Tool Details
`GET /api/v1/tools/{tool_id}`

Retrieves schema and metadata for a tool by its qualified ID (`{server_id}:{tool_name}`) or tool name.

---

### 3.4 Execute Tool
`POST /api/v1/servers/{server_id}/tools/{tool_name}/execute`

Invokes an MCP tool on the server with argument validation and audit logging.

#### Request Body:
```json
{
  "arguments": {
    "expression": "12 + 4 * 2"
  }
}
```

#### Response (`200 OK`):
```json
{
  "execution_id": "a918f62c-63b7-4b71-97b7-5a50785f29d2",
  "server_id": "e427b3b6-733d-4c3e-862d-96116ca31614",
  "tool_name": "calculate",
  "is_error": false,
  "content": [
    {
      "type": "text",
      "text": "20"
    }
  ],
  "structured_content": {
    "result": 20
  },
  "duration_ms": 14.52,
  "executed_at": "2026-10-24T15:05:00Z"
}
```

---

## 4. Execution History Endpoints

### 4.1 List Execution History
`GET /api/v1/executions`

#### Query Parameters:
- `page` *(int, default: 1)*
- `page_size` *(int, default: 20)*
- `server_id` *(UUID, optional)*
- `tool_name` *(string, optional)*
- `is_error` *(bool, optional)*

#### Response (`200 OK`):
```json
{
  "items": [
    {
      "id": "a918f62c-63b7-4b71-97b7-5a50785f29d2",
      "server_id": "e427b3b6-733d-4c3e-862d-96116ca31614",
      "server_name": "local-math-tools",
      "tool_name": "calculate",
      "arguments": {
        "expression": "12 + 4 * 2"
      },
      "is_error": false,
      "error_message": null,
      "duration_ms": 14.52,
      "executed_at": "2026-10-24T15:05:00Z",
      "response": {
        "content": [
          {
            "type": "text",
            "text": "20"
          }
        ]
      }
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

### 4.2 Get Execution Details
`GET /api/v1/executions/{execution_id}`

Returns a single `ExecutionRecord` by its UUID.

---

## 5. System Probes & Telemetry

### 5.1 Liveness Probe
`GET /health`

```json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": "2026-10-24T15:10:00Z"
}
```

### 5.2 Readiness Probe
`GET /ready`

```json
{
  "status": "ready",
  "checks": {
    "repository": true,
    "connection_manager": true
  },
  "timestamp": "2026-10-24T15:10:00Z"
}
```

### 5.3 Operational Metrics
`GET /metrics`

```json
{
  "active_sessions": 1,
  "total_servers": 2,
  "healthy_servers": 1,
  "total_executions": 14,
  "uptime_seconds": 1254.2
}
```

---

## 6. Unified MCP Gateway Endpoint (`/mcp`)

The MCP Hub operates as a unified **Model Context Protocol (MCP) Server** exposing all aggregated tools across connected downstream servers through a standard **Streamable HTTP** transport.

Any MCP-compliant client (Claude Desktop, IDE extensions, autonomous agents, Python MCP SDK client) can connect directly to this endpoint without knowing the downstream server addresses, credentials, or execution environments.

### 6.1 Endpoint Details

- **Protocol:** Model Context Protocol (MCP) JSON-RPC 2.0 over Streamable HTTP
- **URL:** `http://<host>:<port>/mcp`
- **Supported Methods:**
  - `POST /mcp`: JSON-RPC messages (Handshake initialization, tool listing, tool invocation)
  - `GET /mcp`: Server-Sent Events (SSE) stream for real-time notifications
  - `DELETE /mcp`: Graceful session termination
- **Headers:**
  - `mcp-session-id`: Automatically managed session identifier assigned during `initialize`

### 6.2 Tool Namespacing & Identity Mapping

To prevent collisions between identical tool names across different downstream servers (e.g., multiple servers offering `calculate` or `query`), tools exposed through the MCP Gateway are namespaced using sanitized server slug prefixes:

`{sanitized_server_name}__{tool_name}`

**Examples:**
- `math_server__calculate`
- `math_server__echo`
- `text_server__calculate`
- `text_server__text_transform`

If two downstream servers share identical names, the Gateway automatically appends a server UUID suffix to guarantee unique collision-free naming (e.g., `postgres_a1b2c3__query`).

The Hub maintains an explicit internal mapping between:
- Hub Tool Identifier
- Downstream Server ID
- Original MCP Tool Name
- Original JSON Input Schema
- Server Availability Status

### 6.3 Dynamic Tool Discovery (`tools/list`)

When an MCP client requests the tool catalog:
1. The gateway queries all currently enabled and available downstream servers.
2. Discovered tool definitions are retrieved from the cache or refreshed.
3. Descriptions and JSON input schemas are preserved.
4. The client receives the aggregated, namespaced tool list.
5. Connected clients receive `notifications/tools/list_changed` when servers are added, refreshed, or disabled.

### 6.4 Agent-Driven Meta-Tools (`SEARCH_TOOLS` & `MULTI_EXECUTE_TOOLS`)

To support LLM agents orchestrating tools across many servers without exhausting prompt context windows, the Gateway provides two native meta-tools:

#### 6.4.1 `SEARCH_TOOLS` (Pure Discovery)
- **Input Schema:**
  - `queries` (`list[str]`, required, minItems 1): Atomic queries describing required actions.
  - `top_k` (`integer`, optional, default 5, min 1, max 20): Maximum matches per query.
- **Behavior:** Performs token matching and substring-boosted relevance scoring against tool slugs, original names, descriptions, and input schema property names/descriptions. Excludes meta-tools and deduplicates across queries.
- **Response Format (`CallToolResult` text content):**
  ```json
  {
    "matched_count": 1,
    "tools": [
      {
        "tool_slug": "math_server__calculate",
        "server_id": "e427b3b6-733d-4c3e-862d-96116ca31614",
        "description": "Evaluate math expressions",
        "input_schema": {
          "type": "object",
          "properties": {
            "expression": { "type": "string" }
          },
          "required": ["expression"]
        }
      }
    ]
  }
  ```

#### 6.4.2 `MULTI_EXECUTE_TOOLS` (Parallel Dispatcher)
- **Input Schema:**
  - `executions` (`list[object]`, required, minItems 1):
    - `tool_slug` (`string`, required): Canonical namespaced tool slug.
    - `arguments` (`object`, required): Tool input arguments matching schema.
- **Behavior:** Concurrent execution via `asyncio.gather` through `ToolRouterService`. Fully isolates errors per tool call (partial failures do not abort sibling calls). Guarantees audit logging and blocks recursive meta-tool calls.
- **Response Format (`CallToolResult` text content):**
  ```json
  {
    "results": [
      {
        "tool_slug": "math_server__calculate",
        "status": "success",
        "data": "100",
        "error": null
      },
      {
        "tool_slug": "invalid_tool",
        "status": "error",
        "data": null,
        "error": "Unknown or unavailable tool: 'invalid_tool'"
      }
    ]
  }
  ```

### 6.5 Client Usage Example (Python MCP SDK)

```python
import asyncio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    hub_mcp_url = "http://localhost:8000/mcp"

    async with (
        streamable_http_client(hub_mcp_url) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        # 1. Initialize MCP Session
        init_result = await session.initialize()
        print(
            f"Connected to Gateway: {init_result.server_info.name} v{init_result.server_info.version}"
        )

        # 2. Discover Aggregated Tools
        tools_result = await session.list_tools()
        for tool in tools_result.tools:
            print(f"- {tool.name}: {tool.description}")

        # 3. Call Tool on Downstream Server A
        math_result = await session.call_tool(
            "math_server__calculate", arguments={"expression": "10 * 5 + 2"}
        )
        print("Math Result:", math_result.content[0].text)

        # 4. Call Duplicate Tool on Downstream Server B
        text_result = await session.call_tool(
            "text_server__calculate", arguments={"expression": "10 * 5 + 2"}
        )
        print("Server B Result:", text_result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
```
