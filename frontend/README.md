# MCP Hub — Frontend Administration Dashboard

Modern, responsive developer administration console for managing Model Context Protocol (MCP) servers, inspecting unified tool schemas, interactively executing tools through a secure playground, and auditing invocation telemetry.

Built with **Next.js (App Router)**, **React 19**, **TypeScript**, **Tailwind CSS**, **shadcn/ui**, **TanStack Query**, and **Axios**.

---

## 1. Technology Stack

- **Framework:** Next.js (App Router, Server & Client Components)
- **Language:** TypeScript (Strict mode enabled)
- **Styling:** Tailwind CSS with CSS Variables and Dark Mode support
- **UI Components:** shadcn/ui primitives powered by Radix UI
- **Icons:** Lucide React
- **Server State & Caching:** TanStack Query v5
- **HTTP Client:** Axios with custom interceptors and correlation ID propagation (`X-Correlation-ID`)
- **Forms & Validation:** React Hook Form with Zod schemas
- **Theme:** `next-themes` (Light, Dark, and System modes)
- **Notifications:** Sonner toasts
- **Testing:** Vitest & React Testing Library (Unit/Component), Playwright (End-to-End)
- **Package Manager:** pnpm

---

## 2. Project Architecture

Feature-based architecture separating routes, reusable UI components, API integration, and domain features:

```text
frontend/
├── public/
├── src/
│   ├── app/
│   │   ├── layout.tsx                     # Root layout with Providers & Fonts
│   │   ├── page.tsx                       # Redirects to /overview
│   │   ├── globals.css                    # Tailwind & Design tokens
│   │   ├── providers.tsx                  # QueryClient, ThemeProvider, Toaster
│   │   ├── (auth)/                        # login/ and register/ pages (no dashboard shell)
│   │   ├── oauth/complete/page.tsx        # OAuth callback landing: posts the result to the opener or redirects
│   │   └── (dashboard)/
│   │       ├── layout.tsx                 # DashboardShell wrapper
│   │       ├── overview/page.tsx          # Real-time metrics, server health & recent runs
│   │       ├── servers/
│   │       │   ├── page.tsx               # Server list, filtering, sorting, actions
│   │       │   ├── new/page.tsx           # Register new MCP server form
│   │       │   └── [serverId]/
│   │       │       ├── page.tsx           # Server details, health, tools & live test
│   │       │       └── edit/page.tsx      # Edit transport configuration
│   │       ├── tools/
│   │       │   ├── page.tsx               # Unified tool catalog across all servers
│   │       │   └── [toolId]/page.tsx      # Tool schema details & parameters breakdown
│   │       ├── playground/page.tsx        # Interactive tool execution interface
│   │       ├── executions/
│   │       │   ├── page.tsx               # Execution history & audit logs
│   │       │   └── [executionId]/page.tsx # Single execution argument & result view
│   │       ├── sessions/
│   │       │   ├── page.tsx               # Session explorer: agent sessions with status filters
│   │       │   └── [sessionId]/page.tsx   # Session overview and tool-call timeline
│   │       └── settings/page.tsx          # Backend probes and API keys for MCP clients
│   ├── components/
│   │   ├── layout/                        # Sidebar, Header, DashboardShell, AuthGuard
│   │   ├── common/                        # HealthBadge, PageHeader, EmptyState, ErrorAlert, Pagination
│   │   └── ui/                            # shadcn/ui primitives (button, card, dialog, table, etc.)
│   ├── features/
│   │   ├── auth/                          # LoginForm, RegisterForm, ApiKeysCard, use-auth hooks
│   │   ├── overview/                      # Overview metrics components
│   │   ├── servers/                       # ServerForm, RegisterServerDialog, OAuth connect/reconnect, DeletedServerNotice, hooks
│   │   ├── sessions/                      # Session tables, filters, tool-call timeline & detail drawer, hooks
│   │   ├── tools/                         # ToolListTable, ToolFilterBar, hooks
│   │   ├── playground/                    # SchemaForm, ToolPlayground, output viewer
│   │   └── executions/                    # ExecutionListTable, ExecutionFilterBar, hooks
│   ├── lib/
│   │   ├── api-client.ts                  # Centralized Axios instance with correlation IDs
│   │   ├── api/                           # Typed API modules (auth, servers, oauth, tools, executions, sessions, system)
│   │   ├── auth-token.ts                  # Console token in sessionStorage, login redirect helpers
│   │   ├── oauth-complete.ts              # Reads the OAuth callback result
│   │   ├── server-links.ts                # Links to servers from history (which may be deleted)
│   │   ├── errors.ts                      # AppApiError normalized error hierarchy
│   │   └── utils.ts                       # Formatters (duration, dates) & cn class utility
│   ├── schemas/                           # Zod validation schemas
│   ├── types/                             # TypeScript interfaces mirroring FastAPI backend
│   └── test/                              # Vitest unit test suite and test setup
├── .env.example                           # Example environment configuration
├── components.json                        # shadcn/ui configuration
├── next.config.ts                         # Next.js configuration
├── package.json                           # Scripts and dependencies
├── tsconfig.json                          # Strict TypeScript configuration
├── Dockerfile                             # Multi-stage production container
└── README.md
```

---

## 3. Quick Start & Development

### Prerequisites

- Node.js >= 20.x or 22.x
- pnpm >= 10.x

### Installation

```bash
cd frontend
pnpm install
```

### Environment Configuration

Copy `.env.example` to `.env.local`:

```bash
cp .env.example .env.local
```

Ensure `NEXT_PUBLIC_API_BASE_URL` points to your running FastAPI backend:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

### Development Server

```bash
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 4. Scripts & Quality Checks

| Command | Purpose |
| :--- | :--- |
| `pnpm dev` | Start development server on port 3000 |
| `pnpm build` | Run production build and static page generation |
| `pnpm start` | Run Next.js production server |
| `pnpm typecheck` | Run TypeScript strict check (`tsc --noEmit`) |
| `pnpm test` | Run Vitest unit & component test suite |
| `pnpm test:watch` | Run Vitest in interactive watch mode |
| `pnpm test:e2e` | Run Playwright end-to-end tests |

---

## 5. Backend API Endpoints Consumed

The frontend integrates directly with the MCP Hub REST API (full contract: `backend/docs/api-contract.md`). Every call except register and login sends the console token as `Authorization: Bearer <token>`.

### Accounts & API Keys
- `POST /api/v1/auth/register`, `POST /api/v1/auth/login` — Create an account; sign in for a console token.
- `GET /api/v1/auth/me` — The signed-in account (`AuthGuard` waits for it).
- `GET|POST /api/v1/auth/api-keys`, `PATCH|DELETE /api/v1/auth/api-keys/{key_id}` — API keys for MCP clients and their Session idle timeout.
- `GET /api/v1/auth/api-keys/{key_id}/servers/{server_id}/tools`, `PATCH .../tools/{tool_name}` — Which of a server's tools a key can see and run.

### MCP Server Management
- `GET /api/v1/servers` — List servers with search, filtering (`transport`, `health_status`, `enabled`), sorting, and pagination.
- `GET /api/v1/servers/{server_id}` — Get single server configuration and health status.
- `POST /api/v1/servers` — Register a new server (`stdio` or `streamable-http`).
- `PATCH /api/v1/servers/{server_id}` — Update server configuration, descriptions, or toggle execution status.
- `DELETE /api/v1/servers/{server_id}` — Delete server, release active sessions, and purge tools (its execution history is kept).
- `POST /api/v1/servers/{server_id}/test-connection` — Run ephemeral ping check and tool discovery returning latency and tool count.
- `POST /api/v1/servers/{server_id}/refresh-tools` — Connect (with stored OAuth tokens, if any), re-query the server for tools, update the catalog and health.
- `GET /api/v1/servers/{server_id}/tools` — Get tools discovered strictly for the specified server.

### OAuth Connections
- `GET /api/v1/oauth/providers` — Hosted providers that connect with a sign-in, with availability and connection count.
- `POST /api/v1/oauth/connect` — Start a sign-in; returns the authorization URL opened in the popup.
- `POST /api/v1/servers/{server_id}/oauth/reconnect` — Sign in again to a server whose tokens expired (`NEEDS_AUTH`).

### Tool Catalog & Execution
- `GET /api/v1/tools` — Unified tool catalog across all servers with search, server filter, and availability filter.
- `GET /api/v1/tools/{tool_id}` — Retrieve schema and metadata for a tool by its UUID (ids change when a server is re-discovered).
- `POST /api/v1/servers/{server_id}/tools/{tool_name}/execute` — Validate arguments and invoke tool via backend.

### Execution History & Sessions
- `GET /api/v1/executions` — List execution history with filters for `tool_name`, `server_id`, `is_error`, `status`, and pagination.
- `GET /api/v1/executions/{execution_id}` — Full audit record for a single execution, including arguments, response and timing.
- `GET /api/v1/sessions`, `GET /api/v1/sessions/{session_id}`, `GET /api/v1/sessions/{session_id}/tool-calls` — Session explorer.

### Telemetry & Probes
- `GET /api/v1/system/health` — Liveness probe (`status`, `version`, `timestamp`).
- `GET /api/v1/system/ready` — Readiness probe checking repository and connection manager status.
- `GET /api/v1/system/metrics` — Telemetry metrics (`active_sessions`, `total_servers`, `healthy_servers`, `total_executions`, `uptime_seconds`).

---

## 6. Known Gaps

1. **Token refresh:** console tokens expire with no refresh token; an expired token sends the user back to the login page.
2. **Batch / Bulk Actions:** the backend does not provide batch refresh or delete endpoints. The frontend executes these per-server.
3. **Execution Latency Aggregation:** the backend provides total executions in `/metrics`, but no percentiles (p50, p95, p99) or latency timeseries. The frontend derives average execution latency from recent execution records.

---

## 7. Production Docker Deployment

A multi-stage `Dockerfile` is provided for running the Next.js application in production.

### Build and Run Docker Image

```bash
# Build image
docker build -t mcp-hub-frontend:latest \
  --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 .

# Run container on port 3000
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 \
  mcp-hub-frontend:latest
```
