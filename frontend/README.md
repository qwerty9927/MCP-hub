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
│   │       └── settings/page.tsx          # Backend URL, probes, and auth tokens
│   ├── components/
│   │   ├── layout/                        # Sidebar, Header, DashboardShell
│   │   ├── common/                        # HealthBadge, PageHeader, EmptyState, ErrorAlert, Pagination
│   │   └── ui/                            # shadcn/ui primitives (button, card, dialog, table, etc.)
│   ├── features/
│   │   ├── overview/                      # Overview metrics components
│   │   ├── servers/                       # ServerForm, ServerListTable, FilterBar, hooks
│   │   ├── tools/                         # ToolListTable, ToolFilterBar, hooks
│   │   ├── playground/                    # SchemaForm, ToolPlayground, output viewer
│   │   ├── executions/                    # ExecutionListTable, ExecutionFilterBar, hooks
│   │   └── settings/                      # Diagnostic and appearance settings
│   ├── lib/
│   │   ├── api-client.ts                  # Centralized Axios instance with correlation IDs
│   │   ├── api/                           # Typed API client modules (servers, tools, execs, system)
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

The frontend integrates directly with the MCP Hub REST API:

### MCP Server Management
- `GET /api/v1/servers` — List servers with search, filtering (`transport`, `health_status`, `enabled`), sorting, and pagination.
- `GET /api/v1/servers/{server_id}` — Get single server configuration and health status.
- `POST /api/v1/servers` — Register a new server (`stdio` or `streamable-http`).
- `PATCH /api/v1/servers/{server_id}` — Update server configuration, descriptions, or toggle execution status.
- `DELETE /api/v1/servers/{server_id}` — Delete server, release active sessions, and purge tools.
- `POST /api/v1/servers/{server_id}/connect` — Initialize MCP client session and perform tool discovery.
- `POST /api/v1/servers/{server_id}/disconnect` — Gracefully terminate client connection session.
- `POST /api/v1/servers/{server_id}/test-connection` — Run ephemeral ping check and tool discovery returning latency and tool count.
- `POST /api/v1/servers/{server_id}/refresh-tools` — Re-query server for tools and update catalog.
- `GET /api/v1/servers/{server_id}/tools` — Get tools discovered strictly for the specified server.

### Tool Catalog & Execution
- `GET /api/v1/tools` — Unified tool catalog across all servers with search, server filter, and availability filter.
- `GET /api/v1/tools/{tool_id}` — Retrieve schema and metadata for a tool by qualified ID (`{server_id}:{tool_name}`).
- `POST /api/v1/servers/{server_id}/tools/{tool_name}/execute` — Validate arguments and invoke tool via backend.

### Execution History
- `GET /api/v1/executions` — List execution history with filters for `tool_name`, `server_id`, `is_error`, and pagination.
- `GET /api/v1/executions/{execution_id}` — Get full audit record for a single execution including arguments and execution timing.

### Telemetry & Probes
- `GET /api/v1/system/health` — Liveness probe (`status`, `version`, `timestamp`).
- `GET /api/v1/system/ready` — Readiness probe checking repository and connection manager status.
- `GET /api/v1/system/metrics` — Telemetry metrics (`active_sessions`, `total_servers`, `healthy_servers`, `total_executions`, `uptime_seconds`).

---

## 6. Analysis of Backend Capabilities & Integration Requirements

During the inspection of the FastAPI backend and implementation of the dashboard, the following observations and enhancement points were identified:

1. **Authentication & Authorization:**
   - **Current State:** The backend routes are currently unauthenticated (open access).
   - **Frontend Readiness:** The API client includes request interceptors that automatically check and attach `Authorization: Bearer <token>` from volatile session storage (`sessionStorage.getItem("mcp_auth_token")`). When backend auth is introduced (e.g. JWT or API keys), the frontend requires zero refactoring.
2. **Batch / Bulk Actions:**
   - The backend does not currently provide batch connect, disconnect, or delete endpoints. The frontend executes these per-server.
3. **Execution Latency Aggregation:**
   - The backend provides total executions in `/metrics`, but does not provide backend-calculated percentiles (p50, p95, p99) or historical latency timeseries. The frontend derives average execution latency from recent execution records.
4. **Tool Execution Logs Output:**
   - The backend `ExecutionRecord` schema stores `arguments`, `is_error`, `error_message`, and `duration_ms`. The full result content is returned on initial execution response (`ToolExecuteResponse`). If persisted output history is desired in the backend database, the backend schema could optionally retain sanitized output summaries.

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
