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
├── GLOSSARY.md                          # Canonical domain vocabulary
├── pyproject.toml                       # Project metadata, dependencies, Ruff & Pytest config
├── alembic.ini                          # Alembic migration configuration
├── Dockerfile                           # Multi-stage production container build
├── docker-compose.yml                   # Local container orchestration (Postgres + pgvector)
├── .env.example                         # Reference environment variables
├── app/
│   ├── main.py                          # FastAPI factory, ASGI middlewares, lifespan hooks (starts the scheduler)
│   ├── background_service/              # Scheduled background jobs (APScheduler, ADR-0005, ADR-0006)
│   │   ├── scheduler.py                 # create_scheduler(): AsyncIOScheduler + job registration
│   │   ├── session_sweeper.py           # SessionSweeperService: completes idle Sessions (cron job complete-idle-sessions)
│   │   └── embedding_backfill.py        # EmbeddingBackfillService: embeds Tools stored without one (job backfill-tool-embeddings)
│   ├── api/
│   │   ├── dependencies.py              # Centralized dependency injection providers, get_current_principal
│   │   └── v1/                          # API Routers
│   │       ├── auth_router.py           # /auth: register, login, me, API keys
│   │       ├── api_key_tools_router.py  # /auth/api-keys/{id}/servers/{id}/tools: per-key tool visibility (ADR-0007)
│   │       ├── executions_router.py     # Execution audit log endpoints
│   │       ├── oauth_router.py          # /oauth/providers, /oauth/connect, /oauth/callback, /servers/{id}/oauth/reconnect (ADR-0008)
│   │       ├── servers_router.py        # MCP Server registration & lifecycle
│   │       ├── sessions_router.py       # MCP Client session explorer endpoints
│   │       ├── system_router.py         # Liveness, readiness, and telemetry
│   │       └── tools_router.py          # Tool discovery & execution router
│   ├── core/
│   │   ├── config.py                    # Settings loaded strictly from .env (no in-code defaults)
│   │   ├── constants/                   # Application constants partitioned by domain
│   │   │   ├── meta_tools.py            # Meta-tool identifiers (SEARCH_TOOLS, MULTI_EXECUTE_TOOLS)
│   │   │   ├── oauth_constants.py       # OAuth sign-in timeouts, client name, re-authorization reason (ADR-0008)
│   │   │   ├── session_constants.py     # Session idle defaults/bounds, sweep job id and cron schedule
│   │   │   └── tool_search_constants.py # Embedding backfill job id, batch size and interval
│   │   ├── enums/                       # Core enumerations partitioned by domain (no __init__.py)
│   │   │   ├── execution_enum.py        # ExecutionOutcomeKind, RejectionReason
│   │   │   ├── server_enum.py           # TransportType, ServerHealthStatus (incl. NEEDS_AUTH), ServerAuthType
│   │   │   └── session_enum.py          # SessionStatus, ToolCallStatus (incl. `rejected`)
│   │   ├── exceptions.py                # Domain exception hierarchy (derived from AppError)
│   │   └── logging.py                   # Structured correlation-ID logging & contextvars
│   ├── domain/                          # Domain entities partitioned by entity responsibility
│   │   ├── api_key_entity.py            # ApiKeyEntity dataclass
│   │   ├── execution_entity.py          # ExecutionEntity dataclass
│   │   ├── oauth_credential_entity.py   # OAuthCredentialEntity: a server's decrypted OAuth registration and tokens
│   │   ├── principal_entity.py          # Principal: the authenticated caller (account + API key)
│   │   ├── server_entity.py             # ServerEntity dataclass
│   │   ├── session_entity.py            # SessionEntity, SessionDetailEntity, ToolCallEntity
│   │   ├── tool_entity.py               # ToolEntity dataclass
│   │   └── user_entity.py               # UserEntity dataclass
│   ├── helpers/                         # Reusable utilities partitioned by responsibility
│   │   ├── crypto.py                    # SecretCipher: Fernet encryption of stored OAuth credentials
│   │   ├── errors.py                    # MCP error & ExceptionGroup unwrapping (format_mcp_error, find_oauth_error)
│   │   ├── passwords.py                 # Password hashing and verification
│   │   ├── security.py                  # Shell injection, SSRF (incl. DNS resolution), env sanitization, header masking
│   │   ├── session_idle.py              # Session idle-timeout arithmetic (effective timeout, is_idle)
│   │   ├── text.py                      # Slugification & string manipulation (slugify)
│   │   ├── tokens.py                    # Console JWTs, API key generation and hashing (`mhk_` prefix)
│   │   └── validation.py                # Tool arguments JSON-schema validation
│   ├── infrastructure/
│   │   ├── database.py                  # Async SQLAlchemy engine, session maker, connection pooling
│   │   ├── oauth/                       # OAuth connections to hosted MCP servers (ADR-0008)
│   │   │   ├── client_provider.py       # HubOAuthClientProvider, DbTokenStorage/MemoryTokenStorage, client metadata
│   │   │   ├── provider_catalog.py      # OAuthProviderCatalog loaded from the JSON catalog
│   │   │   └── oauth_providers.json     # Curated providers the console offers
│   │   └── repositories/                # Domain repository modules (interfaces, Postgres implementations)
│   │       ├── api_key_repository.py    # ApiKeyRepositoryAbstract, PostgresApiKeyRepository
│   │       ├── execution_repository.py  # ExecutionRepositoryAbstract, PostgresExecutionRepository
│   │       ├── oauth_credential_repository.py # Encrypted OAuth client registration and tokens per server
│   │       ├── server_repository.py     # ServerRepositoryAbstract, PostgresServerRepository
│   │       ├── session_repository.py    # SessionRepositoryAbstract, PostgresSessionRepository
│   │       ├── tool_access_repository.py # Tools hidden from an API key (api_key_disabled_tools)
│   │       ├── tool_repository.py       # ToolRepositoryAbstract, PostgresToolRepository (incl. search_by_embedding)
│   │       └── user_repository.py       # UserRepositoryAbstract, PostgresUserRepository
│   ├── mcp/                             # Upstream MCP protocol extensions & meta-tools
│   │   ├── mcp_proxy_asgi.py            # ASGI proxy: authenticates x-api-key, refuses non-POST, hands off to the SDK
│   │   ├── mcp_server.py                # MCPServer exposing the hub over stateless Streamable HTTP (/mcp)
│   │   ├── multi_execute_tools.py       # MULTI_EXECUTE_TOOLS parallel dispatcher & failure isolator
│   │   └── search_tools.py              # SEARCH_TOOLS discovery handler (vector search through the tool catalog)
│   ├── middlewares/                     # ASGI middleware components
│   │   └── correlation.py               # CorrelationAndLoggingMiddleware (request tracing)
│   ├── models/                          # SQLAlchemy 2.0 ORM models
│   │   ├── api_key_disabled_tool_model.py # Tools hidden from one API key (ADR-0007)
│   │   ├── api_key_model.py             # ApiKeyModel ORM mapping (hash only)
│   │   ├── base_model.py                # Base declarative class
│   │   ├── execution_model.py           # ExecutionModel ORM mapping (no FK to mcp_servers: kept after delete)
│   │   ├── server_model.py              # ServerModel ORM mapping
│   │   ├── server_oauth_credential_model.py # Fernet-encrypted OAuth credentials of one server
│   │   ├── session_model.py             # SessionModel ORM mapping
│   │   ├── tool_model.py                # ToolModel ORM mapping (pgvector embedding column)
│   │   └── user_model.py                # UserModel ORM mapping
│   ├── schemas/                         # Pydantic v2 request/response schemas
│   │   ├── auth_schema.py               # Register/login, tokens, API keys
│   │   ├── common_schema.py             # Paginated envelopes & Error responses
│   │   ├── connection_schema.py         # Stdio & HTTP transport connection schemas
│   │   ├── execution_schema.py          # Execution audit models
│   │   ├── oauth_schema.py              # OAuth providers and connect responses
│   │   ├── server_schema.py             # Server models & validation
│   │   ├── session_schema.py            # Session explorer models
│   │   ├── system_schema.py             # Health & metrics models
│   │   ├── tool_access_schema.py        # Per-API-key tool visibility models
│   │   └── tool_schema.py               # Tool discovery & execution schemas
│   └── services/                        # Business logic & orchestrators
│       ├── auth_service.py              # Accounts, console JWT login, API keys, bearer token -> Principal
│       ├── connection_manager.py        # Downstream MCP client session lifecycle (SessionWorker), incl. OAuth sign-ins (authorize)
│       ├── embedding_service.py         # EmbeddingServiceAbstract, FastEmbedService, tool_embedding_text
│       ├── oauth_service.py             # OAuthService + OAuthFlowRegistry: sign-ins that end in a connected server
│       ├── server_registry.py           # Server CRUD, uniqueness validation, status management
│       ├── session_explorer.py          # Session discovery and execution history
│       ├── session_tracker.py           # Maps each /mcp request to a derived hub Session (ADR-0003, ADR-0004)
│       ├── tool_access_service.py       # Per-API-key tool visibility (ADR-0007)
│       ├── tool_catalog.py              # Tool index over discovered_tools (no in-memory cache), Tool Reference resolution
│       └── tool_executor.py             # Execution module: resolve Tool Reference, check, validate, call, audit (ADR-0002)
├── demo_server/                         # Standalone downstream demo MCP servers (server.py math, server_b.py text)
├── docs/                                # api-contract.md, ADRs (docs/adr/), Postman collection & environment
├── migrations/                          # Alembic schema revision scripts
└── tests/
    ├── conftest.py                      # Pytest async fixtures, test DB setup/cleanup, signed-in clients
    ├── fake_downstream.py               # In-memory stand-in for a downstream Server, at the ConnectionManager seam
    ├── fake_embeddings.py               # FakeEmbeddingService (tests never load the real model)
    ├── fake_oauth_server.py             # OAuth-protected MCP server built from the SDK's auth server
    ├── unit/                            # Fast unit tests (services, helpers, catalog, meta-tools)
    │   ├── test_search_tools.py         # SEARCH_TOOLS discovery & ranking tests
    │   ├── test_multi_execute_tools.py  # MULTI_EXECUTE_TOOLS parallel dispatch & isolation tests
    │   └── ...
    ├── integration/                     # Multi-server aggregation, E2E gateway, OAuth flow, database CRUD
    └── security/                        # SSRF, command injection, executable allowlist tests
```

---

## 4. Key Design Patterns & Invariants

### Clean Layered Architecture
Strict unidirectional dependency flow:
`API Routers (app/api/v1/)` $\rightarrow$ `Services (app/services/)` $\rightarrow$ `Repositories (app/infrastructure/repositories/)` $\rightarrow$ `Database Models (app/models/)`.
- **Routers**: Handle HTTP parameter parsing, status codes, and call services. No business logic in routers.
- **Services**: Contain domain workflows, coordination, validations, and downstream interactions.
- **Repositories**: Abstract all SQL/persistence operations behind `ServerRepositoryAbstract`, `ToolRepositoryAbstract`, `ExecutionRepositoryAbstract`, and `SessionRepositoryAbstract`.
- **Domain Entities**: Transfer state between services and repositories without leaking SQLAlchemy models into external layers.
- **Core Primitives & Enums**: Enums (`app/core/enums/server_enum.py`, `app/core/enums/session_enum.py`, `app/core/enums/execution_enum.py`) and constants (`app/core/constants/meta_tools.py`) reside in `app/core/` to prevent inverted dependencies from domain/model layers into API schemas.
- **Connection Schemas**: Transport configurations (`StdioConfig`, `HttpConfig`, `ConnectionConfigResponse`) are isolated in `app/schemas/connection_schema.py`.

### AnyIO Cancel Scope Rule & `SessionWorker`
- The MCP Python SDK uses AnyIO cancel scopes internally.
- **Invariant**: Never enter an MCP client context manager (`stdio_client`, `streamable_http_client`, `ClientSession`) directly inside an ephemeral HTTP request handler. Doing so causes `RuntimeError: Attempted to exit a cancel scope in a different task than it was entered in`.
- **Rule**: All downstream connections must be spawned and maintained inside a dedicated, long-running `SessionWorker` task managed by `ConnectionManager`. OAuth sign-ins too: `OAuthService` calls `ConnectionManager.authorize`, which runs an ephemeral `SessionWorker` with the sign-in's in-memory auth.

### Streamable HTTP Header Forwarding
- When connecting to remote `streamable-http` servers with authentication headers (e.g. GitHub Copilot, OAuth), pass an `http_client` created via `create_mcp_http_client(headers=server.http_config.headers)` into `streamable_http_client(url, http_client=http_client)`.

### Accounts, Authentication & Ownership
- **Every router depends on the caller**: each endpoint in `app/api/v1/` (except `/auth/register`, `/auth/login`, `/health`, `/ready`) takes `principal: Annotated[Principal, Depends(get_current_principal)]` and passes `user_id=principal.user_id` down. Repository and service methods that read or change owned data take a keyword-only `user_id: UUID` with no default and no `None` (unscoped) mode, so a forgotten owner is a TypeError, not a data leak.
- Another account's resource is a `NotFoundError` (404), never 403, so its existence is not revealed.
- REST accepts only console JWTs (`AuthService.authenticate_console`). `/mcp` accepts only API keys, sent in the `x-api-key` header (`AuthService.authenticate_api_key`), checked in `MCPProxyASGI`, which also sets the SDK's `scope["user"]` so transport sessions are bound to the credential that opened them.
- `user_id` is NOT NULL on `mcp_servers`, `discovered_tools`, `tool_executions`, `server_oauth_credentials` and `mcp_sessions` (foreign key to `users`, cascade delete), and required on their domain entities. `discovered_tools.user_id` and `server_oauth_credentials.user_id` are copies of the server's owner so lookups can be scoped without a join. The only cross-account code is the idle-session sweeper.
- **Ids**: every table's `id` is a UUID stored as `str(UUID)` in `varchar(36)`. The app generates it (`uuid4()` in the entity or service) and `gen_random_uuid()::text` is the database default for inserts made outside the app. `replace_server_tools` replaces a server's Tools on every re-discovery, so Tool ids change then; `(server_id, name)` is unique. There is no `{server_id}:{tool_name}` id; REST names a tool by name plus `server_id`, agents by Tool Slug.
- Settings: `JWT_SECRET` (32+ chars), `ACCESS_TOKEN_EXPIRE_MINUTES`, `ALLOW_SELF_SIGNUP`. Keep `ALLOW_SELF_SIGNUP=false` on any network-exposed deployment: a registered user can add stdio servers.

### Stateless `/mcp` and derived Sessions (ADR-0003, ADR-0004)
- `/mcp` runs the SDK stateless with JSON responses: no transport sessions, no `Mcp-Session-Id` (a client-sent one is ignored), `GET`/`DELETE` answer 405. Do not add features that need a server-to-client channel (sampling, elicitation, notification streams) without revisiting ADR-0004.
- `SessionTracker` derives every Session from account + API key + client name/version (from `_meta`), or the `User-Agent` when the client does not name itself (handshake-era clients). A Session opens on the first `tools/call` (not `tools/list`) and snapshots its API key's `session_idle_minutes` (default `DEFAULT_SESSION_IDLE_SECONDS`) as `idle_timeout_seconds`; it rotates once idle past that (ADR-0005).

### Background jobs (`app/background_service/`, ADR-0005)
- One APScheduler `AsyncIOScheduler` per process, built by `create_scheduler()` and started/shut down in `main.py` `lifespan`; a fresh one per lifespan, since a scheduler cannot restart after shutdown. In-memory job store: jobs are defined in code.
- `complete-idle-sessions` (cron, every minute, `max_instances=1`, `coalesce=True`) runs `SessionSweeperService.complete_idle_sessions`: one idempotent `UPDATE` completing active Sessions idle past their own timeout. It never raises and never touches `last_activity_at`.
- Every job must be safe to run on several hub instances at once. Do not use FastAPI `BackgroundTasks` for periodic work: it only runs after a request.
- Job IDs and schedules live in `app/core/constants/session_constants.py`; shared idle arithmetic in `app/helpers/session_idle.py`.

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
  - Ranking is vector similarity in pgvector (ADR-0006): each query is embedded by `EmbeddingServiceAbstract` (`app/services/embedding_service.py`, local fastembed model) and `ToolRepositoryAbstract.search_by_embedding` returns the caller's `top_k` nearest Tools on enabled Servers by cosine distance, with their `similarity`.
  - Per-API-key visibility (ADR-0007): `/mcp` passes `principal.api_key_id` to `ToolCatalogService.search` and `ToolExecutor.execute`. Tools hidden from that key (`api_key_disabled_tools`, keyed by server and tool name) are left out of the search and rejected on execution (`RejectionReason.TOOL_DISABLED`). Console calls pass no key and are not limited.
  - Tools are embedded from `tool_embedding_text` when their Server is discovered; a failed embedding stores NULL and `EmbeddingBackfillService` (`app/background_service/embedding_backfill.py`, job `backfill-tool-embeddings`, run at startup and every 10 minutes) fills it in. Settings: `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION` (must match the `discovered_tools.embedding` column), `EMBEDDING_CACHE_DIR`. Tests use `tests/fake_embeddings.py` (set in `conftest`), never the real model; the one real-model test runs only with `RUN_SLOW=1`.
  - Automatically excludes `META_TOOL_NAMES` from discovery candidates to avoid self-recursion.
  - Deduplicates matches across queries preserving ranking order.
- **Parallel Dispatcher (`app/mcp/multi_execute_tools.py`)**:
  - `MULTI_EXECUTE_TOOLS` accepts `executions: list[{"tool_slug": str, "arguments": dict[str, Any]}]` (`tool_slug` min length 1, `arguments` defaulting to `{}`).
  - Agent Execution Guidelines instruct LLMs:
    1. Strictly conform `arguments` to the target tool's `input_schema` discovered via `SEARCH_TOOLS`.
    2. Batch independent calls together; do NOT batch data-dependent calls (execute Tool A, inspect its response, then call Tool B in the next turn).
    3. Isolate partial failures and retry only items returning `"validation_error"`.
  - Dispatches calls concurrently via `asyncio.gather(*tasks)` routing each item through `ToolExecutor.execute` (the Execution module), then mapping its Outcome to the item `status`.
  - Complies strictly with the AnyIO Cancel Scope Rule (routes through `ConnectionManager` `SessionWorker`).
  - Preserves argument validation and `ExecutionRepositoryAbstract` audit logging.
  - Strictly isolates failures per execution item (`"status": "success" | "validation_error" | "error"`).
  - Explicitly rejects recursive calls to `META_TOOL_NAMES`.
- **Decoupled Constants (`app/core/constants/meta_tools.py`)**:
  - `SEARCH_TOOLS_NAME`, `MULTI_EXECUTE_TOOLS_NAME`, and `META_TOOL_NAMES = frozenset(...)` decouple tool modules and avoid circular dependencies.

### Error Handling & Exception Groups
- Domain exceptions use a strict 2-level hierarchy inheriting directly from `AppError` (`app/core/exceptions.py`), defining service-agnostic category names (`NotFoundError`, `BadRequestError`, `ConflictError`, `ForbiddenError`, `ValidationError`, `BadGatewayError`, `GatewayTimeoutError`, `InternalServerError`).
- Contextual details (e.g. `server_id`, `tool_name`) are passed through `__init__` parameters rather than defining 3rd-level subclasses. A case callers must tell apart carries a `details["reason"]` constant instead: an OAuth server that needs a new sign-in is a `BadGatewayError` with `OAUTH_REAUTHORIZATION_REASON`, and `ServerRegistryService.record_connect_failure` turns it into health `NEEDS_AUTH`.
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
  - Max line length: `140`.
  - Selected linters: `E` (Pycodestyle errors), `F` (Pyflakes), `I` (isort imports), `UP` (pyupgrade), `B` (flake8-bugbear), `SIM` (flake8-simplify).
  - Ignored: `E501` (line length enforced by formatter), `B008` (function calls in FastAPI argument defaults).

---

## 6. Testing Conventions

- **Runner**: `pytest` with `pytest-asyncio` in auto mode (`asyncio_mode = "auto"`).
- **Test Isolation**: Every test automatically runs the `cleanup_dependencies` fixture in `tests/conftest.py`, which:
  1. Shuts down active connections in `_connection_manager` after the test.
  2. Purges all rows from `discovered_tools`, `tool_executions`, `mcp_sessions`, `mcp_servers`, `api_keys` and `users` (other tables go with them by cascade).
  The schema is created once per run (`init_db()` in a session-scoped fixture). The suite deletes every row in the database it targets: always export `TEST_DATABASE_URL` (conftest no longer falls back to `DATABASE_URL`).
- **Test Client**: `async_client` is signed in as a default account (`user_id` fixture gives its ID; `account_id` creates a bare account for repository-level tests); `other_user_client` is a second account; `anon_client` has no credentials.
- **Test Categories**:
  - `tests/unit/`: Test individual services, repositories (`test_repository.py`), and helpers.
  - `tests/integration/`: Test multi-server orchestration, gateway lifecycle, and real database persistence.
  - `tests/security/`: Test command injection attempts, SSRF blocking, and credential masking.

---

## 7. Open Questions
- **Database Configuration**: Default configuration uses PostgreSQL (`postgresql+asyncpg://postgres:postgres@localhost:5432/mcp_hub`). In `docker-compose.yml`, `backend` connects to the `postgres` container service (`postgresql+asyncpg://postgres:postgres@postgres:5432/mcp_hub`).
