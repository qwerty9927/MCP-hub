/**
 * Backend addresses, all derived from NEXT_PUBLIC_API_BASE_URL in frontend/.env (see .env.example).
 * There is no built-in default: Next.js inlines the value at build time, and next.config.ts stops the build when it is unset.
 * The property access must stay literal (`process.env.NEXT_PUBLIC_API_BASE_URL`) for Next.js to inline it.
 */
const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

if (!apiBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set: add it to frontend/.env (see frontend/.env.example)");
}

/** REST API base, e.g. http://localhost:8000/api/v1: the backend's public address, shown to users and in snippets. */
export const API_BASE_URL: string = apiBaseUrl;

/**
 * Where the console itself sends its API calls: the same path on the console's own origin (e.g. /api/v1).
 * next.config.ts rewrites it to API_PROXY_TARGET, so the refresh token cookie is first-party and reaches /auth/refresh
 * even when the console and the API are on different sites (Vercel), where browsers drop cross-site cookies.
 */
export const API_PROXY_PATH = new URL(API_BASE_URL).pathname.replace(/\/$/, "");

/** The hub's own MCP endpoint (Streamable HTTP), on the same origin as the API. */
export const MCP_ENDPOINT_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, "/mcp");

/** The backend's interactive API docs (Swagger UI). */
export const API_DOCS_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, "/docs");

/**
 * Whether the console shows details about the backend: links to API_DOCS_URL, the API base URL, the backend
 * version and the Settings page's health probes. Production builds hide them (the backend also returns 404 for
 * its docs when ENVIRONMENT=production); `next dev` and tests show them.
 */
export const SHOW_BACKEND_DETAILS = process.env.NODE_ENV !== "production";
