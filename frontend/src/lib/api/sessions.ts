import { apiClient } from "../api-client";
import { PaginatedResponse, SessionDetailRead, SessionFilterParams, SessionRead, SessionToolCallFilterParams, ToolCallRead } from "@/types";

export const sessionsApi = {
    list: async (params?: SessionFilterParams, signal?: AbortSignal): Promise<PaginatedResponse<SessionRead>> => {
        return apiClient<PaginatedResponse<SessionRead>>({
            url: "/sessions",
            method: "GET",
            params,
            signal,
        });
    },

    getById: async (sessionId: string, signal?: AbortSignal): Promise<SessionDetailRead> => {
        return apiClient<SessionDetailRead>({
            url: `/sessions/${sessionId}`,
            method: "GET",
            signal,
        });
    },

    listToolCalls: async (
        sessionId: string,
        params?: SessionToolCallFilterParams,
        signal?: AbortSignal
    ): Promise<PaginatedResponse<ToolCallRead>> => {
        return apiClient<PaginatedResponse<ToolCallRead>>({
            url: `/sessions/${sessionId}/tool-calls`,
            method: "GET",
            params,
            signal,
        });
    },
};
