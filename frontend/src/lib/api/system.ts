import { apiClient } from "../api-client";
import { HealthResponse, MetricsResponse, ReadyResponse } from "@/types";

export const systemApi = {
    health: async (signal?: AbortSignal): Promise<HealthResponse> => {
        return apiClient<HealthResponse>({
            url: "/system/health",
            method: "GET",
            signal,
        });
    },

    readiness: async (signal?: AbortSignal): Promise<ReadyResponse> => {
        return apiClient<ReadyResponse>({
            url: "/system/ready",
            method: "GET",
            signal,
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
