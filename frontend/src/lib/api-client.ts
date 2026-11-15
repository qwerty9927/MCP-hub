import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from "axios";
import { clearAuthToken, getAuthToken, loginPath } from "./auth-token";
import { normalizeApiError } from "./errors";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

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
        const token = getAuthToken();
        if (token && !config.headers["Authorization"]) {
            config.headers["Authorization"] = `Bearer ${token}`;
        }

        return config;
    },
    (error) => Promise.reject(normalizeApiError(error))
);

const PUBLIC_AUTH_PATHS = ["/auth/login", "/auth/register"];

/** An expired or invalid token on any protected call signs the user out and sends them to the login page. */
export function handleUnauthorized(error: unknown): void {
    if (!(error instanceof AxiosError) || error.response?.status !== 401) return;
    const url = error.config?.url ?? "";
    if (PUBLIC_AUTH_PATHS.some((path) => url.endsWith(path))) return;
    clearAuthToken();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.assign(loginPath(window.location.pathname + window.location.search));
    }
}

// Response Interceptor: Normalize all errors
axiosInstance.interceptors.response.use(
    (response) => response,
    (error) => {
        handleUnauthorized(error);
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

export default apiClient;
