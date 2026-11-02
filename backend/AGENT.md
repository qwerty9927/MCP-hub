# AGENT.md — Project Context & Coding Rules

## 1. Project Overview
- **Purpose:** MCP Hub is a production-grade orchestration service that manages multiple Model Context Protocol (MCP) downstream servers (`stdio` and `streamable-http`), aggregates their tools into a unified catalog, and acts as both a REST API hub and an upstream MCP Gateway Server (`POST /mcp`).
- **Tech Stack:** Python 3.12+, FastAPI 0.115+, Model Context Protocol SDK (`mcp` 2.3+), SQLite with `aiosqlite` + SQLAlchemy 2.0 (Asyncio) + Alembic, Pydantic v2 & `pydantic-settings`.
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
│   │   ├── core/
│   │   │   ├── config.py                # Settings loaded strictly from .env (no in-code defaults)
│   │   │   ├── exceptions.py            # Domain exception hierarchy (derived from AppError)
│   │   │   ├── logging.py               # Structured correlation-ID logging & contextvars
│   │   │   └── security.py              # Backward-compatible re-exports from helpers.security
│   │   ├── domain/                      # Domain entities partitioned by entity responsibility
│   │   │   ├── execution.py             # ExecutionEntity dataclass
│   │   │   ├── server.py                # ServerEntity dataclass
│   │   │   └── tool.py                  # ToolEntity dataclass
│   │   ├── helpers/                     # Reusable utilities partitioned by responsibility
│   │   │   ├── errors.py                # MCP error & ExceptionGroup unwrapping (format_mcp_error)
│   │   │   ├── security.py              # Shell injection, SSRF, env sanitization, header masking
│   │   │   ├── text.py                  # Slugification & string manipulation (slugify)
│   │   │   └── validation.py            # Tool arguments JSON-schema validation
│   │   ├── infrastructure/
│   │   │   ├── database.py              # Async SQLAlchemy engine, session maker, SQLite pragmas
│   │   │   └── repositories/            # Repository contracts (base.py) & SQLite impl (sqlite.py)
│   │   ├── middlewares/                 # ASGI middleware components
│   │   │   └── correlation.py           # CorrelationAndLoggingMiddleware (request tracing)
│   │   ├── models/                      # SQLAlchemy 2.0 ORM models (ServerModel, ToolModel, ExecutionModel)
│   │   ├── schemas/                     # Pydantic v2 request/response schemas
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
    ├── unit/                            # Fast unit tests (services, helpers, catalog, registry)
    ├── integration/                     # Multi-server aggregation, E2E gateway, SQLite CRUD
    └── security/                        # SSRF, command injection, executable allowlist tests
```

---

## 4. Key Design Patterns & Invariants

### Clean Layered Architecture
Strict unidirectional dependency flow:
`API Routers (app/api/v1/)` $\rightarrow$ `Services (app/services/)` $\rightarrow$ `Repositories (app/infrastructure/repositories/)` $\rightarrow$ `Database Models (app/models/)`.
- **Routers**: Handle HTTP parameter parsing, status codes, and call services. No business logic in routers.
- **Services**: Contain domain workflows, coordination, validations, and downstream interactions.
- **Repositories**: Abstract all SQL/persistence operations behind `ServerRepositoryBase`, `ToolRepositoryBase`, and `ExecutionRepositoryBase`.
- **Domain Entities**: Transfer state between services and repositories without leaking SQLAlchemy models into external layers.

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

### Error Handling & Exception Groups
- Custom domain exceptions must inherit from `AppError` (`app/core/exceptions.py`), defining a distinct `status_code` and `message`.
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
  - Enforce foreign key constraints via SQLite pragma `PRAGMA foreign_keys=ON`.
- **Ruff Configuration**:
  - Max line length: `100`.
  - Selected linters: `E` (Pycodestyle errors), `F` (Pyflakes), `I` (isort imports), `UP` (pyupgrade), `B` (flake8-bugbear), `SIM` (flake8-simplify).
  - Ignored: `E501` (line length enforced by formatter), `B008` (function calls in FastAPI argument defaults).

---

## 6. Testing Conventions

- **Runner**: `pytest` with `pytest-asyncio` in auto mode (`asyncio_mode = "auto"`).
- **Test Isolation**: Every test automatically runs the `cleanup_dependencies` fixture in `tests/conftest.py`, which:
  1. Initializes the SQLite schema (`init_db()`).
  2. Shuts down active connections in `_connection_manager`.
  3. Purges all rows from `mcp_tools`, `tool_executions`, and `mcp_servers`.
  4. Clears in-memory caches and MCP gateway mappings.
- **Test Client**: Use the `async_client` fixture (`httpx.AsyncClient` with `ASGITransport(app=app)`) for API testing.
- **Test Categories**:
  - `tests/unit/`: Test individual services and helpers with mock repositories.
  - `tests/integration/`: Test multi-server orchestration, gateway lifecycle, and real SQLite persistence.
  - `tests/security/`: Test command injection attempts, SSRF blocking, and credential masking.

---

## 7. Open Questions
- **Database Path in Containers vs. Local**: `.env.example` specifies `DATABASE_URL="sqlite+aiosqlite:///./mcp_hub.db"` (relative path). In `docker-compose.yml`, it points to `sqlite+aiosqlite:///data/mcp_hub.db`. When creating scripts outside of `backend/`, always ensure the working directory is set to `backend/` or use an absolute database path to prevent creating orphan `.db` files.
