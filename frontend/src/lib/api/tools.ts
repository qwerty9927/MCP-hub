import { apiClient } from "../api-client";
import { PaginatedResponse, ToolExecuteRequest, ToolExecuteResponse, ToolFilterParams, ToolRead } from "@/types";

export const toolsApi = {
    list: async (params?: ToolFilterParams, signal?: AbortSignal): Promise<PaginatedResponse<ToolRead>> => {
        return apiClient<PaginatedResponse<ToolRead>>({
            url: "/tools",
            method: "GET",
            params,
            signal,
        });
    },

    getById: async (toolId: string, signal?: AbortSignal): Promise<ToolRead> => {
        return apiClient<ToolRead>({
            url: `/tools/${encodeURIComponent(toolId)}`,
            method: "GET",
            signal,
        });
    },

    execute: async (serverId: string, toolName: string, payload: ToolExecuteRequest): Promise<ToolExecuteResponse> => {
        return apiClient<ToolExecuteResponse>({
            url: `/servers/${serverId}/tools/${encodeURIComponent(toolName)}/execute`,
            method: "POST",
            data: payload,
        });
    },
};
