# MCP Hub

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

## Frontend Quality & Verification Commands

```bash
cd frontend
pnpm typecheck   # Strict TypeScript verification (tsc --noEmit)
pnpm test        # Vitest unit and component test suite
pnpm build       # Optimized Next.js production build
pnpm test:e2e    # Playwright end-to-end tests
```
