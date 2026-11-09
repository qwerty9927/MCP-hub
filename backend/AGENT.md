# AGENT.md — Project Context & Coding Rules

## 1. Project Overview
- **Purpose:** MCP Hub is a production-grade orchestration service that manages multiple Model Context Protocol (MCP) downstream servers (`stdio` and `streamable-http`), aggregates their tools into a unified catalog, and acts as both a REST API hub and an upstream MCP Gateway Server (`POST /mcp`).
- **Tech Stack:** Python 3.12+, FastAPI 0.115+, Model Context Protocol SDK (`mcp` 2.3+), PostgreSQL with `asyncpg` + SQLAlchemy 2.0 (Asyncio) + Alembic, Pydantic v2 & `pydantic-settings`.
- **Package Manager:** `uv` (virtual environment in `backend/.venv`). Monorepo contains Next.js 15 frontend in `frontend/`.

---

## 2. Essential Commands

> All commands must be run from this directory (`backend/`) inside the virtual environment (`.venv`). Prefix with `uv run` or activate the virtualenv.

- **Install dependencies:**
  ```bash
  uv pip install -e ".[dev]"
  ```
- **Run application locally:**
  ```bash
  uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  ```
- **Run all tests:**
  ```bash
  uv run pytest -v
  ```
- **Run a single test (Preferred during iteration):**
  ```bash
  uv run pytest tests/unit/test_helpers.py -k "test_text_slugify" -v
  ```
- **Run a specific test file:**
  ```bash
  uv run pytest tests/unit/test_mcp_gateway.py -v
  ```
- **Lint code:**
  ```bash
  uv run ruff check .
  ```
- **Auto-fix lint issues:**
  ```bash
  uv run ruff check --fix .
  ```
- **Check formatting:**
  ```bash
  uv run ruff format --check .
  ```
- **Format code:**
  ```bash
  uv run ruff format .
  ```
- **Database Migrations:**
  ```bash
  uv run alembic revision --autogenerate -m "describe_change"
  uv run alembic upgrade head
  ```
- **Run built-in demo MCP servers (for testing/integration):**
  ```bash
  uv run python demo_server/server.py     # math server (stdio)
  uv run python demo_server/server_b.py   # text server (stdio)
  ```

---

## 3. Repository Architecture & Module Boundaries

```text
backend/
├── AGENT.md                             # You are here
├── pyproject.toml                       # Project metadata, dependencies, Ruff & Pytest config
├── alembic.ini                          # Alembic migration configuration
├── Dockerfile                           # Multi-stage production container build
├── docker-compose.yml                   # Local container orchestration
├── .env.example                         # Reference environment variables
├── app/
│   │   ├── main.py                      # FastAPI factory, ASGI middlewares, lifespan hooks
│   │   ├── api/
│   │   │   ├── dependencies.py          # Centralized dependency injection providers
│   │   │   └── v1/                      # API Routers (/servers, /tools, /executions, /system)
│   │   │       ├── executions_route.py  # Execution audit log endpoints
│   │   │       ├── servers_route.py     # MCP Server registration & lifecycle
│   │   │       ├── system_route.py      # Liveness, readiness, and telemetry
│   │   │       └── tools_route.py       # Tool discovery & execution router
│   │   ├── core/
│   │   │   ├── config.py                # Settings loaded strictly from .env (no in-code defaults)
│   │   │   ├── constants/               # Application constants partitioned by domain
│   │   │   │   └── meta_tools.py        # Meta-tool identifiers (SEARCH_TOOLS, MULTI_EXECUTE_TOOLS)
│   │   │   ├── enums/                   # Core enumerations partitioned by domain (no __init__.py)
│   │   │   │   └── server_enum.py       # TransportType, ServerHealthStatus
│   │   │   ├── exceptions.py            # Domain exception hierarchy (derived from AppError)
│   │   │   └── logging.py               # Structured correlation-ID logging & contextvars
│   │   ├── domain/                      # Domain entities partitioned by entity responsibility
│   │   │   ├── execution_entity.py      # ExecutionEntity dataclass
│   │   │   ├── server_entity.py         # ServerEntity dataclass
│   │   │   └── tool_entity.py           # ToolEntity dataclass
│   │   ├── helpers/                     # Reusable utilities partitioned by responsibility
│   │   │   ├── errors.py                # MCP error & ExceptionGroup unwrapping (format_mcp_error)
│   │   │   ├── security.py              # Shell injection, SSRF, env sanitization, header masking
│   │   │   ├── text.py                  # Slugification & string manipulation (slugify)
│   │   │   └── validation.py            # Tool arguments JSON-schema validation
│   │   ├── infrastructure/
│   │   │   ├── database.py              # Async SQLAlchemy engine, session maker, connection pooling
│   │   │   └── repositories/            # Domain repository modules (interfaces, Postgres implementations)
│   │   │       ├── server_repo.py       # ServerRepositoryAbstract, PostgresServerRepository
│   │   │       ├── tool_repo.py         # ToolRepositoryAbstract, PostgresToolRepository
│   │   │       └── execution_repo.py    # ExecutionRepositoryAbstract, PostgresExecutionRepository
│   │   ├── mcp/                         # Upstream MCP protocol extensions & meta-tools
│   │   │   ├── search_tools.py          # SEARCH_TOOLS discovery handler & relevance scoring
│   │   │   └── multi_execute_tools.py   # MULTI_EXECUTE_TOOLS parallel dispatcher & failure isolator
│   │   ├── middlewares/                 # ASGI middleware components
│   │   │   └── correlation.py           # CorrelationAndLoggingMiddleware (request tracing)
│   │   ├── models/                      # SQLAlchemy 2.0 ORM models
│   │   │   ├── base_model.py            # Base declarative class
│   │   │   ├── execution_model.py       # ExecutionModel ORM mapping
│   │   │   ├── server_model.py          # ServerModel ORM mapping
│   │   │   └── tool_model.py            # ToolModel ORM mapping
│   │   ├── schemas/                     # Pydantic v2 request/response schemas
│   │   │   ├── common.py                # Paginated envelopes & Error responses
│   │   │   ├── connection.py            # Stdio & HTTP transport connection schemas
│   │   │   ├── execution.py             # Execution audit models
│   │   │   ├── server.py                # Server models & validation
│   │   │   ├── system.py                # Health & metrics models
│   │   │   └── tool.py                  # Tool discovery & execution schemas
│   │   └── services/                    # Business logic & orchestrators
│   │       ├── connection_manager.py    # Downstream MCP client session lifecycle (SessionWorker)
│   │       ├── mcp_gateway.py           # Hub as upstream MCP Server (/mcp Streamable HTTP)
│   │       ├── server_registry.py       # Server CRUD, uniqueness validation, status management
│   │       ├── tool_catalog.py          # Unified tool aggregation cache & collision handler
│   │       └── tool_router.py           # Tool argument validator, execution dispatcher, audit logger
├── demo_server/                         # Standalone downstream demo MCP servers for E2E tests
├── migrations/                          # Alembic schema revision scripts
└── tests/
    ├── conftest.py                      # Pytest async fixtures, test DB cleanup, async_client
    ├── unit/                            # Fast unit tests (services, helpers, catalog, meta-tools)
    │   ├── test_search_tools.py         # SEARCH_TOOLS discovery & ranking tests
    │   ├── test_multi_execute_tools.py  # MULTI_EXECUTE_TOOLS parallel dispatch & isolation tests
    │   └── ...
    ├── integration/                     # Multi-server aggregation, E2E gateway, database CRUD
    └── security/                        # SSRF, command injection, executable allowlist tests
```

---

## 4. Key Design Patterns & Invariants

### Clean Layered Architecture
Strict unidirectional dependency flow:
`API Routers (app/api/v1/)` $\rightarrow$ `Services (app/services/)` $\rightarrow$ `Repositories (app/infrastructure/repositories/)` $\rightarrow$ `Database Models (app/models/)`.
- **Routers**: Handle HTTP parameter parsing, status codes, and call services. No business logic in routers.
- **Services**: Contain domain workflows, coordination, validations, and downstream interactions.
- **Repositories**: Abstract all SQL/persistence operations behind `ServerRepositoryAbstract`, `ToolRepositoryAbstract`, and `ExecutionRepositoryAbstract`.
- **Domain Entities**: Transfer state between services and repositories without leaking SQLAlchemy models into external layers.
- **Core Primitives & Enums**: Enums (`app/core/enums/server_enum.py`) and constants (`app/core/constants/meta_tools.py`) reside in `app/core/` to prevent inverted dependencies from domain/model layers into API schemas.
- **Connection Schemas**: Transport configurations (`StdioConfig`, `HttpConfig`, `ConnectionConfigRead`) are isolated in `app/schemas/connection.py`.

### AnyIO Cancel Scope Rule & `SessionWorker`
- The MCP Python SDK uses AnyIO cancel scopes internally.
- **Invariant**: Never enter an MCP client context manager (`stdio_client`, `streamable_http_client`, `ClientSession`) directly inside an ephemeral HTTP request handler. Doing so causes `RuntimeError: Attempted to exit a cancel scope in a different task than it was entered in`.
- **Rule**: All downstream connections must be spawned and maintained inside a dedicated, long-running `SessionWorker` task managed by `ConnectionManager`.

### Streamable HTTP Header Forwarding
- When connecting to remote `streamable-http` servers with authentication headers (e.g. GitHub Copilot, OAuth), pass an `http_client` created via `create_mcp_http_client(headers=server.http_config.headers)` into `streamable_http_client(url, http_client=http_client)`.

### Configuration Policy (Strict .env Compliance)
- **Invariant**: Do NOT add hardcoded fallback default values for application configuration in `app/core/config.py`. All settings in `Settings` must be explicitly declared and loaded from `.env` or environment variables.

### Security Defenses
- **Stdio Allowlist**: Only executables listed in `ALLOWED_STDIO_EXECUTABLES` can be spawned. Reject any shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `\n`, null bytes).
- **SSRF Protection**: Remote HTTP URLs must be validated via `validate_http_url`. In production (`ALLOW_PRIVATE_NETWORK_HTTP=false`), loopback, link-local, private RFC 1918 subnets, and cloud metadata (`169.254.169.254`) are strictly blocked.
- **Credential Masking**: Sensitive headers (`Authorization`, `x-api-key`, etc.) must always pass through `mask_sensitive_headers()` before serialization in API responses.

### Agent-Driven Meta-Tool Architecture (SEARCH_TOOLS & MULTI_EXECUTE_TOOLS)
- **Design Philosophy**: Keep tools atomic; the upstream Agent is the planner. The hub provides pure discovery and parallel dispatch without backend execution planning.
- **Strict Schema & Runtime Enforcement**:
  - Both schemas enforce `"additionalProperties": False` and runtime Pydantic validation uses `model_config = ConfigDict(extra="forbid")` to reject unadvertised/hallucinated parameters.
  - Tool descriptions are cleaned with `inspect.cleandoc(...)` to eliminate leading indentation whitespace and preserve prompt tokens for upstream LLM contexts.
- **Pure Discovery (`app/mcp/search_tools.py`)**:
  - `SEARCH_TOOLS` accepts atomic queries (`queries: list[str]` with `1..256` character bounds and whitespace trimming) and `top_k: int = 5` (`1..20`).
  - Agent Operating Guidelines embedded in tool description instruct LLMs to:
    1. Emit 1 query per intended action.
    2. Proactively search for hidden prerequisites (e.g., ID lookups before mutations).
    3. Normalize queries without PII or long values.
    4. Use English verbs (`list`, `get`, `search`, `create`, `update`, `delete`, `send`).
  - Relevance scoring evaluates names, descriptions, and JSON schema property names / descriptions with token matching and substring boosting.
  - Automatically excludes `META_TOOL_NAMES` from discovery candidates to avoid self-recursion.
  - Deduplicates matches across queries preserving ranking order.
- **Parallel Dispatcher (`app/mcp/multi_execute_tools.py`)**:
  - `MULTI_EXECUTE_TOOLS` accepts `executions: list[{"tool_slug": str, "arguments": dict[str, Any]}]` (`tool_slug` min length 1, `arguments` defaulting to `{}`).
  - Agent Execution Guidelines instruct LLMs:
    1. Strictly conform `arguments` to the target tool's `input_schema` discovered via `SEARCH_TOOLS`.
    2. Batch independent calls together; do NOT batch data-dependent calls (execute Tool A, inspect its response, then call Tool B in the next turn).
    3. Isolate partial failures and retry only items returning `"validation_error"`.
  - Dispatches calls concurrently via `asyncio.gather(*tasks)` routing through `ToolRouterService.execute_mcp_tool`.
  - Complies strictly with the AnyIO Cancel Scope Rule (routes through `ConnectionManager` `SessionWorker`).
  - Preserves argument validation and `ExecutionRepositoryAbstract` audit logging.
  - Strictly isolates failures per execution item (`"status": "success" | "validation_error" | "error"`).
  - Explicitly rejects recursive calls to `META_TOOL_NAMES`.
- **Decoupled Constants (`app/core/constants/meta_tools.py`)**:
  - `SEARCH_TOOLS_NAME`, `MULTI_EXECUTE_TOOLS_NAME`, and `META_TOOL_NAMES = frozenset(...)` decouple tool modules and avoid circular dependencies.

### Error Handling & Exception Groups
- Domain exceptions use a strict 2-level hierarchy inheriting directly from `AppError` (`app/core/exceptions.py`), defining service-agnostic category names (`NotFoundError`, `BadRequestError`, `ConflictError`, `ForbiddenError`, `ValidationError`, `BadGatewayError`, `GatewayTimeoutError`, `InternalServerError`).
- Contextual details (e.g. `server_id`, `tool_name`) are passed through `__init__` parameters rather than defining 3rd-level subclasses.
- Global exception handling in `app/main.py` populates `ErrorDetail.code` with `str(exc.status_code)`.
- AnyIO and TaskGroups wrap downstream MCP exceptions in nested `ExceptionGroup` objects. Always use `format_mcp_error(exc)` from `app.helpers.errors` to extract clean, actionable error strings for logging and API responses.

---

## 5. Coding & Style Conventions

- **Python Version**: Strictly Python 3.12+.
- **Typing**: Use standard modern Python syntax:
  - `list[str]`, `dict[str, Any]`, `tuple[int, ...]` (no `typing.List` or `typing.Dict`).
  - Union types: `X | None`, `int | float` (no `typing.Optional` or `typing.Union`).
  - Use `datetime.now(UTC)` with `from datetime import UTC` (never use `datetime.utcnow()`).
- **Pydantic**: Use Pydantic v2 patterns (`model_dump()`, `@model_validator(mode="after")`).
- **SQLAlchemy 2.0**:
  - Declarative models use `Mapped[T]` and `mapped_column(...)`.
  - Use async execution: `await session.execute(select(...))`.
  - Native foreign key constraints and cascade deletion in PostgreSQL.
- **Import Style & Package Invariant**:
  - All `__init__.py` files across `app/` are pure package markers (empty, containing 0 re-exports or logic).
  - Internal imports must be explicit and direct to the defining submodule (e.g. `from app.domain.server_entity import ServerEntity`, `from app.infrastructure.repositories.server_repo import ServerRepositoryAbstract`).
- **Ruff Configuration**:
  - Max line length: `100`.
  - Selected linters: `E` (Pycodestyle errors), `F` (Pyflakes), `I` (isort imports), `UP` (pyupgrade), `B` (flake8-bugbear), `SIM` (flake8-simplify).
  - Ignored: `E501` (line length enforced by formatter), `B008` (function calls in FastAPI argument defaults).

---

## 6. Testing Conventions

- **Runner**: `pytest` with `pytest-asyncio` in auto mode (`asyncio_mode = "auto"`).
- **Test Isolation**: Every test automatically runs the `cleanup_dependencies` fixture in `tests/conftest.py`, which:
  1. Initializes the database schema (`init_db()`).
  2. Shuts down active connections in `_connection_manager`.
  3. Purges all rows from `discovered_tools`, `tool_executions`, and `mcp_servers`.
  4. Clears in-memory caches and MCP gateway mappings.
- **Test Client**: Use the `async_client` fixture (`httpx.AsyncClient` with `ASGITransport(app=app)`) for API testing.
- **Test Categories**:
  - `tests/unit/`: Test individual services, repositories (`test_repository.py`), and helpers.
  - `tests/integration/`: Test multi-server orchestration, gateway lifecycle, and real database persistence.
  - `tests/security/`: Test command injection attempts, SSRF blocking, and credential masking.

---

## 7. Open Questions
- **Database Configuration**: Default configuration uses PostgreSQL (`postgresql+asyncpg://postgres:postgres@localhost:5432/mcp_hub`). In `docker-compose.yml`, `backend` connects to the `postgres` container service (`postgresql+asyncpg://postgres:postgres@postgres:5432/mcp_hub`).
