import { AxiosError } from "axios";
import { ApiErrorResponse } from "@/types";

export class AppApiError extends Error {
    public code: string;
    public status?: number;
    public details?: any;
    public correlationId?: string;
    /** Seconds to wait before trying again, from the Retry-After header of a 429. */
    public retryAfterSeconds?: number;

    constructor(
        message: string,
        code = "UNKNOWN_ERROR",
        status?: number,
        details?: any,
        correlationId?: string,
        retryAfterSeconds?: number
    ) {
        super(message);
        this.name = "AppApiError";
        this.code = code;
        this.status = status;
        this.details = details;
        this.correlationId = correlationId;
        this.retryAfterSeconds = retryAfterSeconds;
    }
}

/** HTTP status the backend answers with once a client has used up its sign-in attempts. */
export const TOO_MANY_REQUESTS_STATUS = 429;

/** The Retry-After header as whole seconds; undefined when absent or not a delay in seconds (the backend sends seconds). */
export function parseRetryAfterSeconds(value: unknown): number | undefined {
    if (typeof value !== "string" || !/^\d+$/.test(value.trim())) return undefined;
    return Number(value.trim());
}

export function isRateLimited(error: unknown): error is AppApiError {
    return error instanceof AppApiError && error.status === TOO_MANY_REQUESTS_STATUS;
}

export function normalizeApiError(error: unknown): AppApiError {
    if (error instanceof AppApiError) {
        return error;
    }

    if (error instanceof AxiosError) {
        if (error.code === "ERR_CANCELED" || error.name === "CanceledError") {
            return new AppApiError("Request was canceled", "CANCELED_ERROR");
        }

        const status = error.response?.status;
        const correlationId = error.response?.headers?.["x-correlation-id"] as string | undefined;
        const retryAfterSeconds = parseRetryAfterSeconds(error.response?.headers?.["retry-after"]);
        const data = error.response?.data as ApiErrorResponse | undefined;

        if (data?.error) {
            return new AppApiError(
                data.error.message || "An unexpected error occurred",
                data.error.code || `HTTP_${status}`,
                status,
                data.error.details,
                correlationId,
                retryAfterSeconds
            );
        }

        if (error.code === "ECONNABORTED") {
            return new AppApiError("Request timed out while contacting MCP Hub backend", "TIMEOUT_ERROR", 408);
        }

        if (!error.response) {
            return new AppApiError(
                "Unable to connect to MCP Hub backend. Please ensure the backend is running and CORS is allowed.",
                "NETWORK_ERROR",
                0
            );
        }

        return new AppApiError(error.message || "Request failed", `HTTP_${status}`, status, undefined, correlationId, retryAfterSeconds);
    }

    if (error instanceof Error) {
        return new AppApiError(error.message);
    }

    return new AppApiError("An unknown error occurred");
}
