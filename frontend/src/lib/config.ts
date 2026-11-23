/**
 * Backend addresses, all derived from NEXT_PUBLIC_API_BASE_URL in frontend/.env (see .env.example).
 * There is no built-in default: Next.js inlines the value at build time, and next.config.ts stops the build when it is unset.
 * The property access must stay literal (`process.env.NEXT_PUBLIC_API_BASE_URL`) for Next.js to inline it.
 */
const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

if (!apiBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set: add it to frontend/.env (see frontend/.env.example)");
}

/** REST API base, e.g. http://localhost:8000/api/v1 */
export const API_BASE_URL: string = apiBaseUrl;

/** The hub's own MCP endpoint (Streamable HTTP), on the same origin as the API. */
export const MCP_ENDPOINT_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, "/mcp");

/** The backend's interactive API docs (Swagger UI). */
export const API_DOCS_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, "/docs");
