# AGENT.md — Next.js Project Context & Coding Rules

## 1. Project Overview
- **Purpose:** Centralized administrative dashboard console for Model Context Protocol (MCP) servers. Provides real-time health telemetry, server registration (`stdio` and `streamable-http`), unified tool cataloging, dynamic JSON-schema playground, and audit execution logging.
- **Core Stack:** Next.js 15.2.1 (App Router), React 19.0.0, TypeScript 5.8.2.
- **UI & Styling:** Tailwind CSS 3.4.19 with `tailwindcss-animate`, shadcn/ui (`slate` palette, CSS variables), Radix UI primitives, Lucide Icons (`lucide-react`), `next-themes` (Dark/Light), Sonner toasts.
- **Data & State:** TanStack React Query v5 (`@tanstack/react-query`) for client-side caching/polling/mutations, Axios (`axios`) API client with correlation tracking, decoupled from backend. No Server Actions or Route Handlers; all data routes to FastAPI backend at `NEXT_PUBLIC_API_BASE_URL` (`http://localhost:8000/api/v1`).
- **Auth:** Client-side token authentication hook stubbed in Axios interceptor (`sessionStorage.getItem("mcp_auth_token")` injected into `Authorization: Bearer <token>`). No local database or Next.js middleware.
- **Package Manager:** `pnpm` (version `10.23.0`).

---

## 2. Essential Commands

> All commands must be run from the `frontend/` directory (or prefixed with `pnpm --filter frontend <cmd>`).

- **Install dependencies:**
  ```bash
  pnpm install
  ```
- **Run dev server:**
  ```bash
  pnpm dev
  ```
- **Typecheck (Run before completing any task):**
  ```bash
  pnpm typecheck
  ```
  *(Executes `tsc --noEmit` with strict checking).*
- **Format code:**
  ```bash
  pnpm format
  ```
  *(Applies Prettier with 4-space indentation across all `src/**/*.{ts,tsx,css,json}`).*
- **Run unit & component tests:**
  ```bash
  pnpm test
  ```
  *(Runs Vitest across all `src/**/*.{test,spec}.{ts,tsx}`).*
- **Run a single test file:**
  ```bash
  pnpm test src/test/tool-playground.test.tsx
  ```
- **Run tests in watch mode:**
  ```bash
  pnpm test:watch
  ```
- **Run E2E tests:**
  ```bash
  pnpm test:e2e
  ```
  *(Executes Playwright tests against `http://localhost:3000`).*
- **Production build check (Mandatory verification):**
  ```bash
  pnpm build
  ```

---

## 3. Directory Structure & Architectural Boundaries

```text
frontend/
├── src/
│   ├── app/                            # Next.js 15 App Router
│   │   ├── (dashboard)/                # Dashboard route group (DashboardShell layout)
│   │   │   ├── executions/             # Execution history listing & detail log views
│   │   │   ├── overview/               # Health metrics and platform status dashboard
│   │   │   ├── playground/             # Interactive MCP tool invocation playground
│   │   │   ├── servers/                # Server management (listing, new, edit, detail)
│   │   │   ├── settings/               # System and endpoint connection settings
│   │   │   ├── tools/                  # Unified tool catalog & schema breakdown views
│   │   │   └── layout.tsx              # Shell layout wrapping all dashboard pages
│   │   ├── globals.css                 # Tailwind base styles and CSS variables
│   │   ├── layout.tsx                  # Root Server Component layout with Inter font
│   │   ├── page.tsx                    # Root redirect to /overview
│   │   └── providers.tsx               # Client wrapper: QueryClient, NextThemes, Toaster
│   ├── components/                     # Reusable UI components
│   │   ├── common/                     # Domain-agnostic UI (HealthBadge, PageHeader, ErrorAlert)
│   │   ├── layout/                     # App shell, Top Header, and Navigation Sidebar
│   │   └── ui/                         # shadcn/ui Radix primitives (button, dialog, table, tabs, etc.)
│   ├── features/                       # Domain-driven feature modules
│   │   ├── executions/                 # Execution tables, filters, and useExecutions hook
│   │   ├── overview/                   # Overview metrics dashboard component
│   │   ├── playground/                 # SchemaForm dynamic input builder & ToolPlayground
│   │   ├── servers/                    # ServerForm, ServerListTable, and useServers hooks
│   │   └── tools/                      # ToolListTable, ToolFilterBar, and useTools hooks
│   ├── lib/                            # Shared utilities and backend clients
│   │   ├── api/                        # Typed domain API modules (servers, tools, executions, system)
│   │   ├── api-client.ts               # Axios client instance with X-Correlation-ID & error mapping
│   │   ├── errors.ts                   # AppApiError class and error normalizer
│   │   └── utils.ts                    # cn() class merger, formatDate(), formatDuration()
│   ├── schemas/                        # Zod form validation schemas (server.schema.ts)
│   ├── test/                           # Vitest component tests and setup mocks
│   └── types/                          # Domain and API response interfaces (matches backend)
├── e2e/                                # Playwright end-to-end test specs
└── public/                             # Static public assets
```

---

## 4. React Server Component (RSC) & Client Boundaries

- **Default to RSC for Layouts:**
  - `src/app/layout.tsx` and `src/app/(dashboard)/layout.tsx` are Server Components.
  - Do **not** place `'use client'` on layouts unless local state is strictly required.
  - Root layout injects client state via `<Providers>` wrapper (`src/app/providers.tsx`).
- **Client Components (`'use client'`):**
  - All interactive pages, form inputs, tabs, search filters, and components using React hooks (`useState`, `useEffect`, `useRouter`, `useSearchParams`, `useForm`) must have `'use client'` at the very first line.
  - All components using TanStack Query (`useQuery`, `useMutation`) must be Client Components.
- **Next.js 15 Async Dynamic Route Segment Contract:**
  - In Next.js 15, page `params` and `searchParams` are asynchronous `Promise` objects.
  - Always type page params as `params: Promise<{ id: string }>`:
    ```tsx
    interface PageProps {
        params: Promise<{ serverId: string }>;
    }
    export default function Page({ params }: PageProps) {
        const { serverId } = use(params);
        // ...
    }
    ```
  - When decoding URL-encoded params (e.g. server-qualified tool IDs like `uuid:tool_name`), use safe decoding:
    ```tsx
    let decodedId = toolId;
    try {
        decodedId = decodeURIComponent(toolId);
    } catch {
        decodedId = toolId;
    }
    ```

---

## 5. Data Fetching & Mutation Rules

- **Backend Architecture:**
  - This frontend communicates directly with the FastAPI modular monolith backend (`http://localhost:8000/api/v1`).
  - There are **no** Server Actions (`"use server"`) and **no** internal Next.js Route Handlers (`app/api/`).
- **API Client Layer:**
  - Always invoke endpoints through modular functions in `src/lib/api/*.ts` using `apiClient<T>()`.
  - Every HTTP request must pass through `axiosInstance` in `src/lib/api-client.ts`, which automatically injects an `X-Correlation-ID` header.
- **TanStack Query Conventions:**
  - Encapsulate all queries and mutations inside custom hooks under `src/features/{feature}/hooks/`.
  - Queries must define a standardized query key array (e.g., `["servers", params]`, `["tools", toolId]`).
  - Mutations must invalidate related query keys in `onSuccess`:
    ```tsx
    const queryClient = useQueryClient();
    queryClient.invalidateQueries({ queryKey: ["servers"] });
    ```
  - Do **not** handle error toasts manually in multiple components if the mutation hook already calls `toast.error(err.message)`.

---

## 6. Styling, UI & Formatting Conventions

- **Code Indentation & Formatting:**
  - **4 SPACES** for all indentation (`tabWidth: 4`, `indent_size: 4`). Never use 2 spaces or hard tabs.
  - Double quotes (`"`) for JSX attributes and strings (as configured in `.prettierrc`).
  - Run `pnpm format` before finishing tasks.
- **No Central Constants Anti-Pattern:**
  - Do **not** create a centralized `constants.ts` or global enums file.
  - Define local, strongly-typed TypeScript union types in `src/types/index.ts` (e.g., `TransportType = "stdio" | "streamable-http"`).
- **Tailwind & shadcn/ui:**
  - Combine conditional classes strictly using `cn(...)` from `@/lib/utils`.
  - Prefer semantic theme variables (`bg-card`, `text-card-foreground`, `text-muted-foreground`, `border-border`, `text-primary`, `bg-destructive`).
  - Ensure all form inputs and interactive triggers meet accessibility standards (`aria-label`, accessible focus ring).

---

## 7. Form Handling & Validation

- Use `react-hook-form` with `@hookform/resolvers/zod` for static forms (`ServerForm.tsx`).
- Define validation schemas in `src/schemas/*.schema.ts` using `zod`.
- Dynamic Schema Forms (e.g., tool execution arguments in `SchemaForm.tsx`):
  - Parse JSON Schema dynamically: `string`, `integer`, `number`, `boolean`, `enum`, `array`, `object`.
  - Provide fallback raw JSON editing with syntax validation and "Format JSON" beautification.
  - Highlight missing required parameters before invoking execution endpoints.

---

## 8. Testing Standards

- **Unit & Component Testing (Vitest + React Testing Library):**
  - Test files reside in `src/test/*.test.tsx`.
  - Setup and global DOM mocks are configured in `src/test/setup.ts` (e.g. `ResizeObserver` class mock).
  - Wrap components requiring TanStack Query in a test helper providing `new QueryClient({ defaultOptions: { queries: { retry: false } } })`.
  - When testing Radix UI components, avoid brittle assumptions about DOM menu clicks; test state transitions and mutations directly.
  - When testing Next.js 15 pages that unwrap `Promise` params with `use(params)`, resolve the promise within `act(async () => ...)` or wrap with `<Suspense>`.
- **Pre-Completion Checklist (Run in this order):**
  1. `pnpm typecheck` (Must pass with exit code 0)
  2. `pnpm test` (All tests must pass)
  3. `pnpm build` (Must build production bundles with exit code 0)
  4. `pnpm format` (Ensures 4-space formatting)

---

## 9. Open Questions & Roadmap

- **Authentication Strategy:** The frontend currently stubs JWT attachment via `sessionStorage.getItem("mcp_auth_token")`. Once the backend enables OAuth/JWT login endpoints, integrate authentication session management and login redirect gates.
- **Unified MCP Gateway Live SSE:** Backend exposes SSE streams at `/mcp`. Live client notification handling (e.g. `notifications/tools/list_changed`) will be connected in future telemetry milestones.
