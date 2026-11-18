# MCP Hub Backend

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![MCP SDK](https://img.shields.io/badge/MCP%20SDK-2.3+-orange.svg)](https://modelcontextprotocol.io)

A production-oriented backend for an **MCP Hub** that centrally orchestrates multiple **Model Context Protocol (MCP)** servers, exposes their tools through a unified REST API, and functions as a full-featured **MCP Gateway** exposing aggregated tools over standard Streamable HTTP (`/mcp`).

The backend is decoupled from the frontend, exposing a documented REST API that any compatible frontend (e.g., React SPA) or external client can consume, while allowing standard MCP clients (Claude, IDEs, Python MCP SDK) to connect directly to the hub's `/mcp` endpoint.

---

## Architecture Overview

```mermaid
flowchart TD
    Client["React Frontend / Web Client"] -->|REST API / JSON| FastAPI["FastAPI Application (Port 8000)"]
    MCPClient["Upstream MCP Client (Claude / IDE / SDK)"] -->|Streamable HTTP (/mcp)| MCPGateway["MCP Gateway Service (/mcp)"]
    
    subgraph FastAPI Application
        FastAPI --> Auth["Middleware & Security Validation"]
        Auth --> Routers["API Routers (/api/v1)"]
        FastAPI --> MCPGateway
        
        subgraph Routers
            R_Servers["/servers"]
            R_Tools["/tools"]
            R_Exec["/executions"]
            R_Sys["/health, /ready, /metrics"]
        end
        
        subgraph Services Layer
            ServerRegistry["Server Registry Service"]
            ToolCatalog["Unified Tool Catalog (Tool IDs & Slugs)"]
            ToolExecutor["Execution Module (Resolve, Validate, Call & Audit)"]
            ConnManager["Connection Manager (SessionWorker per server)"]
            MCPGateway
        end
        
        subgraph Repositories & Storage
            ServerRepo[("PostgreSQL Server Repository")]
            ToolRepo[("PostgreSQL Tool Repository")]
            ExecRepo[("PostgreSQL Execution Repository")]
        end
    end
    
    R_Servers --> ServerRegistry
    R_Tools --> ToolCatalog
    R_Tools --> ToolExecutor
    
    MCPGateway --> ServerRegistry
    MCPGateway --> ToolCatalog
    MCPGateway --> ToolExecutor
    
    ToolExecutor --> ConnManager
    ToolExecutor --> ExecRepo
    ServerRegistry --> ServerRepo
    ServerRegistry --> ConnManager
    ToolCatalog --> ToolRepo
    ToolCatalog --> ConnManager
    
    subgraph Downstream MCP Servers
        ConnManager -->|stdio (subprocess)| StdioServer["Local MCP Server A (e.g. math_server)"]
        ConnManager -->|stdio / streamable-http| StdioServerB["Downstream MCP Server B (e.g. text_server)"]
    end
```

### Architectural Highlights

1. **MCP Gateway (Hub as Server)**: The hub acts as both an MCP client (connecting downstream) and an MCP server exposing aggregated tools through a single Streamable HTTP endpoint (`/mcp`). Downstream tools are dynamically discovered, namespaced (`{server_slug}__{tool_name}`), collision-proofed, and forwarded with full fidelity.
2. **SessionWorker Isolation**: MCP client sessions use AnyIO cancel scopes internally. To prevent cross-task cancel scope errors in asynchronous web servers, each active MCP connection runs inside a dedicated `SessionWorker` task. The worker enters and exits its `AsyncExitStack` within the same task and holds the session open until it is told to stop; tool calls use that session under a per-server concurrency limit (`MAX_CONCURRENT_EXECUTIONS_PER_SERVER`).
3. **Multi-Transport Support**: First-class support for both `stdio` (subprocess pipelines) and `streamable-http` (HTTP streaming endpoints) using the official `mcp` 2.x SDK.
4. **Unified Tool Catalog**: Tools discovered from heterogeneous MCP servers are indexed into a consolidated catalog stored in PostgreSQL and read from the database on every lookup (no in-memory cache). Every tool has a UUID id (new on each re-discovery) and an embedding for semantic search; cross-server naming collisions are resolved by the server in the REST path (`/servers/{server_id}/tools/{tool_name}`) and by namespaced slugs (`{server_slug}__{tool_name}`) in the MCP Gateway.
5. **Defense-in-Depth Security**:
   - Stdio commands restricted to the executables listed in `ALLOWED_STDIO_EXECUTABLES`.
   - Command injection defense and argument validation.
   - SSRF protection rejecting private IP ranges, loopback, and cloud metadata endpoints (`169.254.169.254`).
   - Automatic masking of sensitive headers and credentials in API outputs.
   - Clean environment sanitization preventing host secrets from leaking into child processes.
6. **Agent-Driven Meta-Tool Architecture**:
   Exposes two native meta-tools on `/mcp` designed for autonomous upstream agents:
   - `SEARCH_TOOLS`: Semantic discovery: queries and tools are embedded by a local fastembed model and ranked by cosine similarity in pgvector (ADR-0006). Excludes meta-tools to prevent recursion and returns deduplicated candidate tools, best match first, with their `similarity`.
   - `MULTI_EXECUTE_TOOLS`: Parallel dispatcher executing multiple tool calls concurrently via `asyncio.gather` through `ToolExecutor` (the Execution module). Provides per-tool failure isolation (a failed downstream call does not fail sibling executions) while strictly preserving AnyIO cancel scopes, JSON schema validation, and database audit logging.
7. **Accounts and API Keys**: Every Server, Tool, Execution and Session belongs to one account, and another account's resource is a 404. The REST API accepts only console login tokens (JWT); `/mcp` accepts only API keys (`x-api-key`). Each key can hide individual Tools (ADR-0007) and sets the idle timeout of the Sessions it opens (ADR-0005).
8. **OAuth Connections**: Hosted MCP servers that need OAuth are connected from a curated provider catalog. The MCP SDK runs discovery, client registration, PKCE and refresh; tokens are stored Fernet-encrypted, and a server whose tokens can no longer be refreshed is marked `NEEDS_AUTH` until the owner signs in again (ADR-0008).

---

## Project Structure

```text
backend/
├── app/
│   ├── main.py                # FastAPI application factory & lifespan (starts the background scheduler)
│   ├── api/v1/                # Routers: auth, API-key tool visibility, servers, OAuth, tools, executions, sessions, system
│   ├── background_service/    # APScheduler jobs: idle-session sweeper, embedding backfill
│   ├── core/                  # Settings, constants, enums, exceptions, logging
│   ├── domain/                # Dataclass entities passed between layers
│   ├── helpers/               # Security (allowlist, SSRF), tokens, passwords, crypto, validation
│   ├── infrastructure/        # Database engine, Postgres repositories, OAuth client glue & provider catalog
│   ├── mcp/                   # /mcp gateway: auth proxy, MCPServer, SEARCH_TOOLS, MULTI_EXECUTE_TOOLS
│   ├── middlewares/           # Correlation ID & request logging
│   ├── models/                # SQLAlchemy 2.0 ORM models
│   ├── schemas/               # Pydantic v2 request/response schemas
│   └── services/              # Auth, connection manager, catalog, executor, sessions, OAuth, embeddings
├── demo_server/               # Demo downstream MCP servers (server.py: math, server_b.py: text)
├── docs/                      # api-contract.md, ADRs (docs/adr/), Postman collection
├── migrations/                # Alembic revisions
├── tests/                     # unit/, integration/, security/ plus fakes (downstream, embeddings, OAuth server)
├── Dockerfile
├── docker-compose.yml         # Backend + PostgreSQL with pgvector
├── pyproject.toml
└── .env.example
```

See [`AGENT.md`](AGENT.md) for the file-by-file module map, and [`GLOSSARY.md`](GLOSSARY.md) for the domain terms.

---

## Getting Started

### Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) (recommended for fast installation) or standard `pip`
- Docker & Docker Compose (optional for containerized deployment)

### 1. Installation

Clone the repository and set up a virtual environment:

```bash
# Navigate to backend directory
cd backend

# Create virtual environment with Python 3.12
uv venv --python 3.12 .venv
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"
```

Alternatively with pip:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure Environment

Copy the example configuration:
```bash
cp .env.example .env
```

Every setting is required; there are no in-code defaults. The ones to review first:
```ini
ENVIRONMENT="development"
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/mcp_hub"
ALLOWED_STDIO_EXECUTABLES=["python", "python3", "python3.12", "uv", "node", "npx", "bun", "docker"]
ALLOW_PRIVATE_NETWORK_HTTP=true    # false on any network-exposed deployment (SSRF protection)
JWT_SECRET="<32+ random characters>"
ALLOW_SELF_SIGNUP=true             # false on any network-exposed deployment: a registered user can add stdio servers
OAUTH_ENCRYPTION_KEY="<Fernet key>"  # see the command in .env.example; rotating it makes stored OAuth tokens unreadable
PUBLIC_API_BASE_URL="http://localhost:8000"   # the OAuth callback is built from it
FRONTEND_BASE_URL="http://localhost:3000"
```

### 3. Run Database Migrations (Alembic)

Initialize or upgrade the PostgreSQL database schema. The database must have the pgvector extension available (for example the `pgvector/pgvector:pg17` image); the migrations run `CREATE EXTENSION IF NOT EXISTS vector`:

```bash
alembic upgrade head
```

On first start the backend downloads the tool-search embedding model (`EMBEDDING_MODEL`, about 64 MB) into `EMBEDDING_CACHE_DIR`.

### 4. Run the Backend

Start the FastAPI application with Uvicorn:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Once running:
- **Interactive OpenAPI Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## Running with Docker Compose

To launch the containerized backend with PostgreSQL + pgvector (`pgvector/pgvector:pg17`):

```bash
cd backend
docker compose up --build
```

---

## Running Tests

The suite deletes every row in the database it runs against, so point it at a separate test database first. `conftest.py` reads `TEST_DATABASE_URL` and never falls back to `DATABASE_URL`:

```bash
cd backend
export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/mcp_hub_test"
uv run pytest -v
```

Run test suite with code coverage analysis:

```bash
uv run pytest --cov=app --cov-report=term-missing
```

Run code formatting and linting check with Ruff:

```bash
ruff check .
```

---

## Verification & API Walkthrough

Here is a step-by-step walkthrough to test the hub using `curl`. Every REST endpoint except register, login, `/health` and `/ready` needs a console login token; `/mcp` needs an API key instead.

### 0. Create an Account and Sign In
Registration needs `ALLOW_SELF_SIGNUP=true`.
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@example.com", "password": "change-me-123"}'

curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@example.com", "password": "change-me-123"}'
```
Save the returned `access_token` (e.g. `TOKEN="<access_token>"`). It expires after `ACCESS_TOKEN_EXPIRE_MINUTES`; log in again to get a new one.

### 1. Register the Demo MCP Server
```bash
curl -X POST http://localhost:8000/api/v1/servers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "demo-server",
    "description": "Local Demo MCP Server",
    "transport": "stdio",
    "stdio_config": {
      "command": "python3",
      "args": ["demo_server/server.py"]
    },
    "enabled": true
  }'
```

Save the returned `id` (e.g. `SERVER_ID="<returned-uuid>"`).

### 2. Test Server Connection
```bash
curl -X POST "http://localhost:8000/api/v1/servers/$SERVER_ID/test-connection" \
  -H "Authorization: Bearer $TOKEN"
```
Response:
```json
{
  "success": true,
  "message": "Successfully connected to 'demo-server'. Discovered 3 tools.",
  "tools_count": 3,
  "latency_ms": 35.2
}
```

### 3. Connect and Discover Tools
```bash
curl -X POST "http://localhost:8000/api/v1/servers/$SERVER_ID/connect" \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Query the Unified Tool Catalog
```bash
curl "http://localhost:8000/api/v1/tools" \
  -H "Authorization: Bearer $TOKEN"
```
Returns all of the account's tools across enabled servers (`calculate`, `echo`, `system_ping`).

### 5. Execute Tool: `calculate`
```bash
curl -X POST "http://localhost:8000/api/v1/servers/$SERVER_ID/tools/calculate/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "expression": "42 * 2 + 16"
    }
  }'
```
Response:
```json
{
  "execution_id": "c61b9a21-9310-45e0-9112-9c1c69c645ba",
  "server_id": "e427b3b6-733d-4c3e-862d-96116ca31614",
  "tool_name": "calculate",
  "is_error": false,
  "content": [
    {
      "type": "text",
      "text": "100"
    }
  ],
  "structured_content": {
    "result": 100
  },
  "duration_ms": 11.23,
  "executed_at": "2026-10-24T15:15:00Z"
}
```

### 6. Inspect Execution History
```bash
curl "http://localhost:8000/api/v1/executions" \
  -H "Authorization: Bearer $TOKEN"
```

### 7. Upstream Agent Meta-Tools via `/mcp` (Streamable HTTP)

When AI agents connect to the hub's upstream endpoint (`POST /mcp`), they can discover and batch execute tools without loading entire catalogs into context.

`/mcp` accepts only API keys, never the console token. Generate one (the full key is shown only once):
```bash
curl -X POST http://localhost:8000/api/v1/auth/api-keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "laptop Claude"}'
```
Configure the MCP client with the hub URL `http://localhost:8000/mcp` and the returned `key` (`mhk_...`) in the `x-api-key` header. The endpoint is stateless: it accepts `POST` only and issues no `Mcp-Session-Id` (ADR-0004). Use one key per client, so the Session explorer can tell clients apart (ADR-0003).

#### Discovery: `SEARCH_TOOLS`
Call `SEARCH_TOOLS` with atomic search queries:
```json
{
  "name": "SEARCH_TOOLS",
  "arguments": {
    "queries": ["math expression", "text transform"],
    "top_k": 5
  }
}
```
Response:
```json
{
  "matched_count": 2,
  "tools": [
    {
      "tool_slug": "demo_server__calculate",
      "server_id": "e427b3b6-733d-4c3e-862d-96116ca31614",
      "description": "Calculate math expressions",
      "input_schema": {
        "type": "object",
        "properties": {
          "expression": { "type": "string" }
        },
        "required": ["expression"]
      }
    },
    {
      "tool_slug": "text_server__text_transform",
      "server_id": "7b13e9a2-9310-45e0-9112-9c1c69c645ba",
      "description": "Transform text case",
      "input_schema": {
        "type": "object",
        "properties": {
          "text": { "type": "string" },
          "mode": { "type": "string", "enum": ["uppercase", "lowercase"] }
        },
        "required": ["text"]
      }
    }
  ]
}
```

#### Parallel Execution: `MULTI_EXECUTE_TOOLS`
Execute multiple discovered tools concurrently with isolated per-tool error reporting:
```json
{
  "name": "MULTI_EXECUTE_TOOLS",
  "arguments": {
    "executions": [
      {
        "tool_slug": "demo_server__calculate",
        "arguments": { "expression": "25 * 4 + 10" }
      },
      {
        "tool_slug": "text_server__text_transform",
        "arguments": { "text": "hello world", "mode": "uppercase" }
      }
    ]
  }
}
```
Response:
```json
{
  "results": [
    {
      "tool_slug": "demo_server__calculate",
      "status": "success",
      "data": "110",
      "error": null
    },
    {
      "tool_slug": "text_server__text_transform",
      "status": "success",
      "data": "HELLO WORLD",
      "error": null
    }
  ]
}
```

---

## Frontend Integration

The backend is decoupled from any specific frontend UI. For detailed endpoint signatures, pagination envelopes, error models, and example payloads for React client developers, refer to [`docs/api-contract.md`](docs/api-contract.md).
