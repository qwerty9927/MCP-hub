import { AxiosError } from "axios";
import { ApiErrorResponse } from "@/types";

export class AppApiError extends Error {
    public code: string;
    public status?: number;
    public details?: any;
    public correlationId?: string;

    constructor(message: string, code = "UNKNOWN_ERROR", status?: number, details?: any, correlationId?: string) {
        super(message);
        this.name = "AppApiError";
        this.code = code;
        this.status = status;
        this.details = details;
        this.correlationId = correlationId;
    }
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
        const data = error.response?.data as ApiErrorResponse | undefined;

        if (data?.error) {
            return new AppApiError(
                data.error.message || "An unexpected error occurred",
                data.error.code || `HTTP_${status}`,
                status,
                data.error.details,
                correlationId
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

        return new AppApiError(error.message || "Request failed", `HTTP_${status}`, status, undefined, correlationId);
    }

    if (error instanceof Error) {
        return new AppApiError(error.message);
    }

    return new AppApiError("An unknown error occurred");
}
