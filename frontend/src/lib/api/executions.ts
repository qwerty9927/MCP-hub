import { apiClient } from "../api-client";
import {
    CallTimeseries,
    CallTimeseriesParams,
    ExecutionFilterParams,
    ExecutionRecord,
    PaginatedResponse,
    ToolUsageParams,
    ToolUsageReport,
} from "@/types";

export const executionsApi = {
    list: async (params?: ExecutionFilterParams, signal?: AbortSignal): Promise<PaginatedResponse<ExecutionRecord>> => {
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

    toolUsage: async (params: ToolUsageParams, signal?: AbortSignal): Promise<ToolUsageReport> => {
        return apiClient<ToolUsageReport>({
            url: "/executions/tool-usage",
            method: "GET",
            params,
            signal,
        });
    },

    timeseries: async (params: CallTimeseriesParams, signal?: AbortSignal): Promise<CallTimeseries> => {
        return apiClient<CallTimeseries>({
            url: "/executions/timeseries",
            method: "GET",
            params,
            signal,
        });
    },
};
