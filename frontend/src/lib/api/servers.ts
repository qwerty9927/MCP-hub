import { apiClient } from "../api-client";
import {
    PaginatedResponse,
    ServerCreate,
    ServerFilterParams,
    ServerRead,
    ServerTestResponse,
    ServerUpdate,
    ToolFilterParams,
    ToolRead,
} from "@/types";

export const serversApi = {
    list: async (
        params?: ServerFilterParams,
        signal?: AbortSignal
    ): Promise<PaginatedResponse<ServerRead>> => {
        return apiClient<PaginatedResponse<ServerRead>>({
            url: "/servers",
            method: "GET",
            params,
            signal,
        });
    },

    getById: async (serverId: string, signal?: AbortSignal): Promise<ServerRead> => {
        return apiClient<ServerRead>({
            url: `/servers/${serverId}`,
            method: "GET",
            signal,
        });
    },

    create: async (payload: ServerCreate): Promise<ServerRead> => {
        return apiClient<ServerRead>({
            url: "/servers",
            method: "POST",
            data: payload,
        });
    },

    update: async (serverId: string, payload: ServerUpdate): Promise<ServerRead> => {
        return apiClient<ServerRead>({
            url: `/servers/${serverId}`,
            method: "PATCH",
            data: payload,
        });
    },

    delete: async (serverId: string): Promise<void> => {
        return apiClient<void>({
            url: `/servers/${serverId}`,
            method: "DELETE",
        });
    },

    connect: async (serverId: string): Promise<ServerRead> => {
        return apiClient<ServerRead>({
            url: `/servers/${serverId}/connect`,
            method: "POST",
        });
    },

    disconnect: async (serverId: string): Promise<ServerRead> => {
        return apiClient<ServerRead>({
            url: `/servers/${serverId}/disconnect`,
            method: "POST",
        });
    },

    testConnection: async (serverId: string): Promise<ServerTestResponse> => {
        return apiClient<ServerTestResponse>({
            url: `/servers/${serverId}/test-connection`,
            method: "POST",
        });
    },

    refreshTools: async (serverId: string): Promise<ToolRead[]> => {
        return apiClient<ToolRead[]>({
            url: `/servers/${serverId}/refresh-tools`,
            method: "POST",
        });
    },

    getTools: async (
        serverId: string,
        params?: ToolFilterParams,
        signal?: AbortSignal
    ): Promise<PaginatedResponse<ToolRead>> => {
        return apiClient<PaginatedResponse<ToolRead>>({
            url: `/servers/${serverId}/tools`,
            method: "GET",
            params,
            signal,
        });
    },
};
