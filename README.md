# MCP Hub

[![Backend CI](https://github.com/qwerty9927/MCP-hub/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/qwerty9927/MCP-hub/actions/workflows/backend-ci.yml)
[![Frontend CI](https://github.com/qwerty9927/MCP-hub/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/qwerty9927/MCP-hub/actions/workflows/frontend-ci.yml)

Centralized platform for Model Context Protocol (MCP) server management, tool cataloging, and unified REST API invocation.

- **Backend:** [`backend/`](backend/) — FastAPI modular monolith with official MCP 2.x SDK, multi-transport support (`stdio`, `streamable-http`), security controls, and full test suite.
- **Frontend:** [`frontend/`](frontend/) — Modern Next.js App Router administrative console with real-time health telemetry, server management, dynamic schema playground, and execution history.
- **API Documentation:** [`backend/docs/api-contract.md`](backend/docs/api-contract.md)

---

## Quick Start

### 1. Backend (FastAPI)

```bash
cd backend
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

Interactive API documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Frontend (Next.js)

```bash
cd frontend
pnpm install
cp .env.example .env.local
pnpm dev
```

Dashboard administration console will be available at [http://localhost:3000](http://localhost:3000).

---

## Running the Whole Stack with Docker Compose

[`docker-compose.yml`](docker-compose.yml) runs PostgreSQL (with pgvector), the backend and the console together. Each app reads its own env file, the same one you use when running it locally:

- `backend` reads `backend/.env` (all backend settings). Compose overrides only `DATABASE_URL`, so the backend uses the `db` container instead of `localhost`.
- `frontend` reads `frontend/.env`. `next build` inlines `NEXT_PUBLIC_API_BASE_URL` from it into the browser bundle and bakes in the `API_PROXY_TARGET` rewrite, so rebuild with `docker compose up --build` after changing either. Compose sets `API_PROXY_TARGET` to `http://backend:8000`.

```bash
cp backend/.env.example backend/.env                 # skip if you already have one; fill in JWT_SECRET and OAUTH_ENCRYPTION_KEY
cp frontend/.env.example frontend/.env               # skip if you already have one
docker compose up --build
```

| Service    | Image / build                     | Host port | Notes |
| ---------- | --------------------------------- | --------- | ----- |
| `db`       | `pgvector/pgvector:pg17`          | none      | Data in the `postgres_data` volume; `docker compose exec db psql -U postgres mcp_hub` |
| `backend`  | [`backend/Dockerfile`](backend/Dockerfile)   | `8000`    | Starts once `db` is healthy; runs `alembic upgrade head`, then uvicorn. API docs at [http://localhost:8000/docs](http://localhost:8000/docs) |
| `frontend` | [`frontend/Dockerfile`](frontend/Dockerfile) | `3000`    | Next.js standalone server; starts once `backend` is healthy. Console at [http://localhost:3000](http://localhost:3000) |

**First user.** Open [http://localhost:3000/register](http://localhost:3000/register) and create an account, then sign in. This needs `ALLOW_SELF_SIGNUP=true` in `backend/.env`. On anything reachable from a network, set it to `false` once your account exists and run `docker compose up -d`, because any registered user can add stdio servers.

**Addresses.**
- **Console API calls:** the browser sends them to the console's own origin (`/api/v1/...`), and the console's server forwards them to `API_PROXY_TARGET`. This keeps the refresh token cookie first-party, so sign-in survives new and duplicated tabs even when the console and the API are on different sites (for example on Vercel).
- **`NEXT_PUBLIC_API_BASE_URL`:** the backend's public address (`http://localhost:8000/api/v1`). The console shows it in the MCP endpoint, the API key config and the code snippets, and its path must match the backend's `API_V1_STR`.
- **Backend:** `FRONTEND_BASE_URL` in `backend/.env` must be the console's address (`http://localhost:3000`), and `CORS_ORIGINS` should include it.

**Compose overrides (optional).** A root `.env` (see [`.env.example`](.env.example)) can change the database credentials (`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`, default `postgres`/`postgres`/`mcp_hub`; the database port is not published), point `POSTGRES_DATA` at an existing Postgres 17 data folder instead of the `postgres_data` volume (stop any other Postgres using it first) and the host ports (`BACKEND_PORT`, `FRONTEND_PORT`). Don't put backend setting names there: the backend also reads `../.env` when run from `backend/`.

**stdio MCP servers.** The backend starts stdio servers as subprocesses inside its own container, so only runtimes in the backend image can be used:

- **Included:** `python` / `python3` (the backend's Python 3.12 virtualenv), `uv` / `uvx`, and Node.js 22 with `node` / `npm` / `npx`. Packages fetched by `npx` or `uvx` are downloaded on first use, so the container needs internet access.
- **Not included:** `docker` (no Docker CLI or socket in the container) and `bun`. If `ALLOWED_STDIO_EXECUTABLES` in `backend/.env` lists them, a server that uses them is accepted but fails to start. Add a runtime to `backend/Dockerfile` if you need it.
- A stdio server's command and files must exist inside the container. A script path on your machine won't work unless you mount it into the `backend` service.

**Other notes.**
- To reach a streamable-http server running on your machine, use `http://host.docker.internal:<port>` (Docker Desktop), with `ALLOW_PRIVATE_NETWORK_HTTP=true` in `backend/.env`.
- `ENVIRONMENT=production` in `backend/.env` turns on DNS-rebinding protection for the hub's own `/mcp` endpoint, which then only accepts `localhost` / `127.0.0.1` / `[::1]` as the Host. Clients that reach the hub under another hostname are rejected until the backend's allowed hosts are made configurable, or you use `development`.
- `docker compose down` stops the stack and keeps the data. `docker compose down -v` also deletes the database volume.
- [`backend/docker-compose.yml`](backend/docker-compose.yml) still runs just the backend and database from `backend/`. Its data lives in a separate volume.

---

## Frontend Quality & Verification Commands

```bash
cd frontend
pnpm typecheck   # Strict TypeScript verification (tsc --noEmit)
pnpm test        # Vitest unit and component test suite
pnpm build       # Optimized Next.js production build
pnpm test:e2e    # Playwright end-to-end tests
```

---

## Continuous Integration

GitHub Actions runs on every pull request and on pushes to `main`, for the side that changed:

- **Backend CI** ([`.github/workflows/backend-ci.yml`](.github/workflows/backend-ci.yml)): `ruff check`, `ruff format --check`, Alembic migrations against an empty database, and the full `pytest` suite on Postgres with pgvector.
- **Frontend CI** ([`.github/workflows/frontend-ci.yml`](.github/workflows/frontend-ci.yml)): `pnpm typecheck`, `pnpm format:check`, `pnpm test` and `pnpm build`.

The Playwright e2e specs are not run in CI yet.
