import { describe, it, expect } from "vitest";
import { normalizeApiError, AppApiError } from "@/lib/errors";
import { AxiosError } from "axios";

describe("API Error Normalization", () => {
    it("preserves AppApiError instances", () => {
        const error = new AppApiError("Custom error message", "CUSTOM_CODE", 400);
        const normalized = normalizeApiError(error);
        expect(normalized).toBe(error);
        expect(normalized.message).toBe("Custom error message");
        expect(normalized.code).toBe("CUSTOM_CODE");
        expect(normalized.status).toBe(400);
    });

    it("normalizes backend error envelope correctly", () => {
        const axiosError = new AxiosError(
            "Request failed with status code 404",
            "ERR_BAD_REQUEST",
            undefined,
            {},
            {
                status: 404,
                statusText: "Not Found",
                headers: { "x-correlation-id": "test-corr-id-999" },
                config: {} as any,
                data: {
                    error: {
                        code: "ServerNotFoundError",
                        message: "Server with id 'abc-123' not found",
                        details: { server_id: "abc-123" },
                    },
                },
            }
        );

        const normalized = normalizeApiError(axiosError);
        expect(normalized.message).toBe("Server with id 'abc-123' not found");
        expect(normalized.code).toBe("ServerNotFoundError");
        expect(normalized.status).toBe(404);
        expect(normalized.details).toEqual({ server_id: "abc-123" });
        expect(normalized.correlationId).toBe("test-corr-id-999");
    });

    it("handles network failures gracefully", () => {
        const axiosError = new AxiosError("Network Error", "ERR_NETWORK");
        const normalized = normalizeApiError(axiosError);
        expect(normalized.code).toBe("NETWORK_ERROR");
        expect(normalized.message).toContain("Unable to connect to MCP Hub backend");
    });

    it("handles timeout aborts gracefully", () => {
        const axiosError = new AxiosError("timeout of 30000ms exceeded", "ECONNABORTED");
        const normalized = normalizeApiError(axiosError);
        expect(normalized.code).toBe("TIMEOUT_ERROR");
        expect(normalized.status).toBe(408);
    });
});
