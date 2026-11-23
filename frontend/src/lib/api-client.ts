import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from "axios";
import { clearAuthToken, getAuthToken, loginPath, setAuthToken } from "./auth-token";
import { normalizeApiError } from "./errors";
import { API_BASE_URL } from "./config";
import { TokenResponse } from "@/types";

/**
 * /auth/refresh and /auth/logout act on the refresh token cookie, so the backend also requires this header (its CSRF check).
 * Sent with `withCredentials` so the browser includes the httpOnly cookie on these cross-origin calls.
 */
export const CONSOLE_CLIENT_HEADERS = { "X-MCP-Hub-Client": "console" } as const;

/** The Web Lock that serialises refreshes across tabs: tabs share one cookie, and the backend treats a second use of a rotated token as theft. */
export const REFRESH_LOCK_NAME = "mcp-hub-refresh";

interface AuthRequestConfig extends InternalAxiosRequestConfig {
    /** Set on the one retry after a refresh, so a second 401 signs out instead of looping. */
    _authRetried?: boolean;
    /** Set on the refresh call itself: its 401 is handled by whoever asked for the refresh. */
    _skipAuthHandling?: boolean;
}

export const axiosInstance: AxiosInstance = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
    },
});

// Request Interceptor: Attach correlation ID and future auth tokens
axiosInstance.interceptors.request.use(
    (config) => {
        // Generate correlation ID if not set
        if (!config.headers["X-Correlation-ID"]) {
            config.headers["X-Correlation-ID"] =
                typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `req-${Date.now()}`;
        }

        // Console login token from POST /auth/login
        // (not on the refresh call: the token it would attach is the expired one)
        const token = getAuthToken();
        if (token && !config.headers["Authorization"] && !(config as AuthRequestConfig)._skipAuthHandling) {
            config.headers["Authorization"] = `Bearer ${token}`;
        }

        return config;
    },
    (error) => Promise.reject(normalizeApiError(error))
);

const PUBLIC_AUTH_PATHS = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout"];

function isPublicAuthPath(url: string | undefined): boolean {
    return PUBLIC_AUTH_PATHS.some((path) => (url ?? "").endsWith(path));
}

/** An expired or invalid token on any protected call signs the user out and sends them to the login page. */
export function handleUnauthorized(error: unknown): void {
    if (!(error instanceof AxiosError) || error.response?.status !== 401) return;
    if (isPublicAuthPath(error.config?.url)) return;
    clearAuthToken();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.assign(loginPath(window.location.pathname + window.location.search));
    }
}

let refreshInFlight: Promise<string | null> | null = null;

/**
 * Exchange the refresh token cookie for a new access token and store it; null when the sign-in is over.
 * Concurrent callers in this tab share one request, and the Web Lock makes other tabs wait their turn,
 * so each refresh sends the cookie the previous one set.
 */
export function refreshSession(): Promise<string | null> {
    if (!refreshInFlight) {
        refreshInFlight = withRefreshLock(requestNewAccessToken).finally(() => {
            refreshInFlight = null;
        });
    }
    return refreshInFlight;
}

// Response Interceptor: refresh once on a 401, then normalize all errors
axiosInstance.interceptors.response.use(
    (response) => response,
    async (error) => {
        if (shouldRefresh(error)) {
            const retried = await retryAfterRefresh(error);
            if (retried) return retried;
        }
        if (!(error instanceof AxiosError && (error.config as AuthRequestConfig | undefined)?._skipAuthHandling)) {
            handleUnauthorized(error);
        }
        return Promise.reject(normalizeApiError(error));
    }
);

export async function apiClient<T>(config: AxiosRequestConfig): Promise<T> {
    try {
        const response = await axiosInstance.request<T>(config);
        return response.data;
    } catch (error) {
        throw normalizeApiError(error);
    }
}

async function requestNewAccessToken(): Promise<string | null> {
    try {
        const config: Partial<AuthRequestConfig> = {
            url: "/auth/refresh",
            method: "POST",
            withCredentials: true,
            headers: new axios.AxiosHeaders({ ...CONSOLE_CLIENT_HEADERS }),
            _skipAuthHandling: true,
        };
        const response = await axiosInstance.request<TokenResponse>(config);
        setAuthToken(response.data.access_token);
        return response.data.access_token;
    } catch {
        return null;
    }
}

function withRefreshLock<T>(task: () => Promise<T>): Promise<T> {
    const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
    if (!locks?.request) return task();
    return locks.request(REFRESH_LOCK_NAME, task) as Promise<T>;
}

/** A 401 worth one refresh: from a protected endpoint, and not already the retry. */
function shouldRefresh(error: unknown): error is AxiosError & { config: AuthRequestConfig } {
    if (!(error instanceof AxiosError) || error.response?.status !== 401 || !error.config) return false;
    const config = error.config as AuthRequestConfig;
    return !config._authRetried && !config._skipAuthHandling && !isPublicAuthPath(config.url);
}

async function retryAfterRefresh(error: AxiosError & { config: AuthRequestConfig }) {
    const config = error.config;
    config._authRetried = true;
    // Another request may have refreshed while this one was in flight: reuse that token rather than rotating again.
    const current = getAuthToken();
    const sent = config.headers?.["Authorization"];
    const token = current && sent !== `Bearer ${current}` ? current : await refreshSession();
    if (!token) return null;
    config.headers["Authorization"] = `Bearer ${token}`;
    return axiosInstance.request(config);
}

export default apiClient;
