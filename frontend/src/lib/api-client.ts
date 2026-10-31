import axios, { AxiosInstance, AxiosRequestConfig } from "axios";
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
                typeof crypto !== "undefined" && crypto.randomUUID
                    ? crypto.randomUUID()
                    : `req-${Date.now()}`;
        }

        // Auth hook: If an auth token is in memory or localStorage in the future, attach here
        if (typeof window !== "undefined") {
            const token = sessionStorage.getItem("mcp_auth_token");
            if (token && !config.headers["Authorization"]) {
                config.headers["Authorization"] = `Bearer ${token}`;
            }
        }

        return config;
    },
    (error) => Promise.reject(normalizeApiError(error))
);

// Response Interceptor: Normalize all errors
axiosInstance.interceptors.response.use(
    (response) => response,
    (error) => Promise.reject(normalizeApiError(error))
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
