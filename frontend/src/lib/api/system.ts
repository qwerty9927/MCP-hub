import { apiClient } from "../api-client";
import { HealthResponse, MetricsResponse, ReadyResponse } from "@/types";

export const systemApi = {
    health: async (): Promise<HealthResponse> => {
        return apiClient<HealthResponse>({
            url: "/system/health",
            method: "GET",
        });
    },

    readiness: async (): Promise<ReadyResponse> => {
        return apiClient<ReadyResponse>({
            url: "/system/ready",
            method: "GET",
        });
    },

    metrics: async (): Promise<MetricsResponse> => {
        return apiClient<MetricsResponse>({
            url: "/system/metrics",
            method: "GET",
        });
    },
};
