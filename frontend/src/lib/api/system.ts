import { apiClient } from "../api-client";
import { HealthResponse, MetricsResponse, ReadyResponse } from "@/types";

const HTTP_OK = 200;
const HTTP_SERVICE_UNAVAILABLE = 503;

export const systemApi = {
    health: async (signal?: AbortSignal): Promise<HealthResponse> => {
        return apiClient<HealthResponse>({
            url: "/system/health",
            method: "GET",
            signal,
        });
    },

    /** 200 `ready` or 503 `not_ready`: both carry the probe's checks, so a 503 resolves instead of throwing. */
    readiness: async (signal?: AbortSignal): Promise<ReadyResponse> => {
        return apiClient<ReadyResponse>({
            url: "/system/ready",
            method: "GET",
            signal,
            validateStatus: (status) => status === HTTP_OK || status === HTTP_SERVICE_UNAVAILABLE,
        });
    },

    metrics: async (signal?: AbortSignal): Promise<MetricsResponse> => {
        return apiClient<MetricsResponse>({
            url: "/system/metrics",
            method: "GET",
            signal,
        });
    },
};
