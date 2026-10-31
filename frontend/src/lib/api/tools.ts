import { apiClient } from "../api-client";
import {
    PaginatedResponse,
    ToolExecuteRequest,
    ToolExecuteResponse,
    ToolFilterParams,
    ToolRead,
} from "@/types";

export const toolsApi = {
    list: async (params?: ToolFilterParams): Promise<PaginatedResponse<ToolRead>> => {
        return apiClient<PaginatedResponse<ToolRead>>({
            url: "/tools",
            method: "GET",
            params,
        });
    },

    getById: async (toolId: string): Promise<ToolRead> => {
        return apiClient<ToolRead>({
            url: `/tools/${encodeURIComponent(toolId)}`,
            method: "GET",
        });
    },

    execute: async (
        serverId: string,
        toolName: string,
        payload: ToolExecuteRequest
    ): Promise<ToolExecuteResponse> => {
        return apiClient<ToolExecuteResponse>({
            url: `/servers/${serverId}/tools/${encodeURIComponent(toolName)}/execute`,
            method: "POST",
            data: payload,
        });
    },
};
