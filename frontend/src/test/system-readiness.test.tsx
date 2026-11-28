import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { axiosInstance } from "@/lib/api-client";
import { systemApi } from "@/lib/api";
import { AppApiError } from "@/lib/errors";
import SystemSettingsPage from "@/app/(dashboard)/settings/system/page";

const NOT_READY = { status: "not_ready", checks: { database: false }, timestamp: "2026-11-28T00:00:00Z" };

/** An adapter answering every request with `status`, applying validateStatus the way axios's own adapters do. */
function answerWith(status: number, data: unknown) {
    return async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
        const response: AxiosResponse = { data, status, statusText: String(status), headers: {}, config, request: {} };
        if (config.validateStatus && !config.validateStatus(status)) {
            throw new AxiosError(`Request failed with status code ${status}`, "ERR_BAD_RESPONSE", config, {}, response);
        }
        return response;
    };
}

function renderPage() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={client}>
            <SystemSettingsPage />
        </QueryClientProvider>
    );
}

const originalAdapter = axiosInstance.defaults.adapter;

afterEach(() => {
    axiosInstance.defaults.adapter = originalAdapter;
    vi.restoreAllMocks();
});

describe("systemApi.readiness", () => {
    it("returns the probe body when the backend answers 503 not_ready", async () => {
        axiosInstance.defaults.adapter = answerWith(503, NOT_READY);

        await expect(systemApi.readiness()).resolves.toEqual(NOT_READY);
    });

    it("still rejects other failures", async () => {
        axiosInstance.defaults.adapter = answerWith(500, { error: { code: "InternalServerError", message: "boom" } });

        await expect(systemApi.readiness()).rejects.toMatchObject({ status: 500 });
    });
});

describe("System settings readiness", () => {
    it("says the database is unreachable when the probe reports not_ready", async () => {
        vi.spyOn(systemApi, "health").mockResolvedValue({ status: "ok", version: "0.1.0" } as never);
        vi.spyOn(systemApi, "readiness").mockResolvedValue(NOT_READY);
        renderPage();

        expect(await screen.findByText("Not ready: database unreachable")).toBeInTheDocument();
    });

    it("says the backend is unreachable when the probe itself fails", async () => {
        vi.spyOn(systemApi, "health").mockResolvedValue({ status: "ok", version: "0.1.0" } as never);
        vi.spyOn(systemApi, "readiness").mockRejectedValue(new AppApiError("Unable to connect", "NETWORK_ERROR", 0));
        renderPage();

        const readyRow = (await screen.findByText("GET /ready")).parentElement!;
        expect(await screen.findAllByText("Unreachable")).not.toHaveLength(0);
        expect(readyRow).toHaveTextContent("Unreachable");
    });

    it("shows ready when every check passes", async () => {
        vi.spyOn(systemApi, "health").mockResolvedValue({ status: "ok", version: "0.1.0" } as never);
        vi.spyOn(systemApi, "readiness").mockResolvedValue({ status: "ready", checks: { database: true }, timestamp: NOT_READY.timestamp });
        renderPage();

        expect(await screen.findByText("Ready (checks passing)")).toBeInTheDocument();
    });
});
