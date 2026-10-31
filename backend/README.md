# MCP Hub Backend

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![MCP SDK](https://img.shields.io/badge/MCP%20SDK-2.3+-orange.svg)](https://modelcontextprotocol.io)
[![Tests Passing](https://img.shields.io/badge/tests-50%20passed-brightgreen.svg)]()
[![Coverage 88%](https://img.shields.io/badge/coverage-88%25-green.svg)]()

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
            ToolCatalog["Unified Tool Catalog (Cache & Qualified IDs)"]
            ToolRouter["Tool Execution Router (Validation & Auditing)"]
            ConnManager["Connection Manager (SessionWorker per server)"]
            MCPGateway
        end
        
        subgraph Repositories & Storage
            ServerRepo[("SQLite Server Repository")]
            ToolRepo[("SQLite Tool Repository")]
            ExecRepo[("SQLite Execution Repository")]
        end
    end
    
    R_Servers --> ServerRegistry
    R_Tools --> ToolCatalog
    R_Tools --> ToolRouter
    
    MCPGateway --> ServerRegistry
    MCPGateway --> ToolCatalog
    MCPGateway --> ToolRouter
    
    ToolRouter --> ConnManager
    ToolRouter --> ExecRepo
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
2. **SessionWorker Isolation**: MCP client sessions use AnyIO cancel scopes internally. To prevent cross-task cancel scope errors in asynchronous web servers, each active MCP connection runs inside a dedicated `SessionWorker` task. The worker enters and exits its `AsyncExitStack` within the same task while concurrently processing requests via asyncio queues and synchronization primitives.
3. **Multi-Transport Support**: First-class support for both `stdio` (subprocess pipelines) and `streamable-http` (HTTP streaming endpoints) using the official `mcp` 2.x SDK.
4. **Unified Tool Catalog**: Tools discovered from heterogeneous MCP servers are indexed into a consolidated catalog with persistent SQLite storage and caching. Cross-server naming collisions are resolved using server-qualified identifiers (`{server_id}:{tool_name}`) in REST and namespaced slugs in MCP Gateway.
5. **Defense-in-Depth Security**:
   - **Database Encryption at Rest**: Sensitive fields (`stdio_config.env`, `http_config.headers`, execution `arguments`) are automatically encrypted using AES-128-CBC and HMAC-SHA256 (Fernet) before writing to SQLite storage, with transparent ORM decryption and zero-compromise raw SQL inspection.
   - Stdio commands restricted to an approved executable allowlist (`python`, `uv`, `node`, `npx`, `docker`).
   - Command injection defense and argument validation.
   - SSRF protection rejecting private IP ranges, loopback, and cloud metadata endpoints (`169.254.169.254`).
   - Automatic masking of sensitive headers and credentials in API outputs.
   - Clean environment sanitization preventing host secrets from leaking into child processes.

---

## Project Structure

```text
backend/
├── app/
│   ├── main.py                          # FastAPI application factory & lifespan
│   ├── api/
│   │   ├── dependencies.py              # Dependency injection providers
│   │   └── v1/
│   │       ├── servers.py               # MCP Server registration & lifecycle
│   │       ├── tools.py                 # Tool discovery & execution router
│   │       ├── executions.py            # Execution audit log endpoints
│   │       └── system.py                # Liveness, readiness, and telemetry
│   ├── core/
│   │   ├── config.py                    # Pydantic v2 application settings
│   │   ├── security.py                  # SSRF & command injection defenses
│   │   ├── logging.py                   # Structured correlation-ID logging
│   │   └── exceptions.py                # Domain exception hierarchy
│   ├── domain/
│   │   └── entities.py                  # Domain dataclasses & entities
│   ├── schemas/
│   │   ├── common.py                    # Paginated envelopes & Error responses
│   │   ├── server.py                    # Server models & validation
│   │   ├── tool.py                      # Tool discovery & execution schemas
│   │   ├── execution.py                 # Execution audit models
│   │   └── system.py                    # Health & metrics models
│   ├── services/
│   │   ├── server_registry.py           # Server CRUD business logic
│   │   ├── connection_manager.py        # Process & stream session orchestration
│   │   ├── tool_catalog.py              # Cross-server tool aggregation cache
│   │   ├── tool_router.py               # Input validation & execution router
│   │   └── mcp_gateway.py               # MCP Gateway server & Streamable HTTP transport
│   └── infrastructure/
│       └── repositories/
│           ├── base.py                  # Abstract repository contracts
│           └── memory.py                # Thread-safe in-memory repositories
├── demo_server/
│   └── server.py                        # Built-in demo MCP server (3 tools)
├── docs/
│   └── api-contract.md                  # Comprehensive REST API contract
├── tests/
│   ├── conftest.py                      # Test fixtures & test clients
│   ├── unit/                            # Unit test suite
│   ├── integration/                     # Full lifecycle stdio & HTTP tests
│   └── security/                        # Security validation tests
├── Dockerfile                           # Production multi-stage Docker build
├── docker-compose.yml                   # Docker Compose setup
├── pyproject.toml                       # Pinned dependencies & tooling configs
├── .env.example                         # Environment configuration template
└── README.md
```

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

Key environment options in `.env`:
```ini
PROJECT_NAME="MCP Hub Backend"
ENVIRONMENT="development"
PORT=8000
ALLOWED_STDIO_EXECUTABLES=["python", "python3", "uv", "node", "npx"]
ALLOW_PRIVATE_NETWORK_HTTP=true
```

### 3. Run Database Migrations (Alembic)

Initialize or upgrade the SQLite database schema:

```bash
alembic upgrade head
```

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

To launch the containerized backend with SQLite persistent volume:

```bash
cd backend
docker compose up --build
```

---

## Running Tests

Execute the complete test suite (unit, integration, and security tests):

```bash
cd backend
pytest -v
```

Run test suite with code coverage analysis:

```bash
pytest --cov=app --cov-report=term-missing
```

Run code formatting and linting check with Ruff:

```bash
ruff check .
```

---

## Verification & API Walkthrough

Here is a step-by-step walkthrough to test the hub using `curl`:

### 1. Register the Demo MCP Server
```bash
curl -X POST http://localhost:8000/api/v1/servers \
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
curl -X POST "http://localhost:8000/api/v1/servers/$SERVER_ID/test-connection"
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
curl -X POST "http://localhost:8000/api/v1/servers/$SERVER_ID/connect"
```

### 4. Query the Unified Tool Catalog
```bash
curl "http://localhost:8000/api/v1/tools"
```
Returns all tools across enabled servers (`calculate`, `echo`, `system_ping`).

### 5. Execute Tool: `calculate`
```bash
curl -X POST "http://localhost:8000/api/v1/servers/$SERVER_ID/tools/calculate/execute" \
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
curl "http://localhost:8000/api/v1/executions"
```

---

## Frontend Integration

The backend is decoupled from any specific frontend UI. For detailed endpoint signatures, pagination envelopes, error models, and example payloads for React client developers, refer to [`docs/api-contract.md`](docs/api-contract.md).
