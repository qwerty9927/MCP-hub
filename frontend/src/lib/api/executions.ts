import { apiClient } from "../api-client";
import { ExecutionFilterParams, ExecutionRecord, PaginatedResponse } from "@/types";

export const executionsApi = {
    list: async (params?: ExecutionFilterParams): Promise<PaginatedResponse<ExecutionRecord>> => {
        return apiClient<PaginatedResponse<ExecutionRecord>>({
            url: "/executions",
            method: "GET",
            params,
        });
    },

    getById: async (executionId: string): Promise<ExecutionRecord> => {
        return apiClient<ExecutionRecord>({
            url: `/executions/${executionId}`,
            method: "GET",
        });
    },
};
