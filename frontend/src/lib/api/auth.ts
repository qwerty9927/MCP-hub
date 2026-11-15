import { apiClient } from "../api-client";
import { ApiKeyCreated, ApiKeyRead, LoginRequest, RegisterRequest, TokenResponse, UserRead } from "@/types";

export const authApi = {
    register: async (payload: RegisterRequest): Promise<UserRead> => {
        return apiClient<UserRead>({ url: "/auth/register", method: "POST", data: payload });
    },
    login: async (payload: LoginRequest): Promise<TokenResponse> => {
        return apiClient<TokenResponse>({ url: "/auth/login", method: "POST", data: payload });
    },
    me: async (signal?: AbortSignal): Promise<UserRead> => {
        return apiClient<UserRead>({ url: "/auth/me", method: "GET", signal });
    },
    listApiKeys: async (signal?: AbortSignal): Promise<ApiKeyRead[]> => {
        return apiClient<ApiKeyRead[]>({ url: "/auth/api-keys", method: "GET", signal });
    },
    createApiKey: async (name: string, sessionIdleMinutes: number | null = null): Promise<ApiKeyCreated> => {
        return apiClient<ApiKeyCreated>({
            url: "/auth/api-keys",
            method: "POST",
            data: { name, session_idle_minutes: sessionIdleMinutes },
        });
    },
    /** Change how long a Session opened with this key may sit idle (null = default). Applies to Sessions opened afterwards. */
    updateApiKey: async (keyId: string, sessionIdleMinutes: number | null): Promise<ApiKeyRead> => {
        return apiClient<ApiKeyRead>({
            url: `/auth/api-keys/${keyId}`,
            method: "PATCH",
            data: { session_idle_minutes: sessionIdleMinutes },
        });
    },
    revokeApiKey: async (keyId: string): Promise<void> => {
        return apiClient<void>({ url: `/auth/api-keys/${keyId}`, method: "DELETE" });
    },
};
