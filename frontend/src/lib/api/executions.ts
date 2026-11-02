import { apiClient } from "../api-client";
import { ExecutionFilterParams, ExecutionRecord, PaginatedResponse } from "@/types";

export const executionsApi = {
    list: async (
        params?: ExecutionFilterParams,
        signal?: AbortSignal
    ): Promise<PaginatedResponse<ExecutionRecord>> => {
        return apiClient<PaginatedResponse<ExecutionRecord>>({
            url: "/executions",
            method: "GET",
            params,
            signal,
        });
    },

    getById: async (executionId: string, signal?: AbortSignal): Promise<ExecutionRecord> => {
        return apiClient<ExecutionRecord>({
            url: `/executions/${executionId}`,
            method: "GET",
            signal,
        });
    },
};
