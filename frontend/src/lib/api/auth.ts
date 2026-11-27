import { apiClient, CONSOLE_CLIENT_HEADERS } from "../api-client";
import {
    ApiKeyCreated,
    ApiKeyRead,
    ApiKeyTool,
    ApiKeyToolVisibility,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
} from "@/types";

export const authApi = {
    register: async (payload: RegisterRequest): Promise<UserRead> => {
        return apiClient<UserRead>({ url: "/auth/register", method: "POST", data: payload });
    },
    /** Also sets the httpOnly refresh token cookie (first-party, through the console's API proxy). */
    login: async (payload: LoginRequest): Promise<TokenResponse> => {
        return apiClient<TokenResponse>({ url: "/auth/login", method: "POST", data: payload, withCredentials: true });
    },
    /** Revoke the sign-in of the refresh token cookie and clear the cookie. The server always answers 204. */
    logout: async (): Promise<void> => {
        return apiClient<void>({ url: "/auth/logout", method: "POST", withCredentials: true, headers: { ...CONSOLE_CLIENT_HEADERS } });
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
    /** A server's tools with whether each is visible to this key. */
    listServerTools: async (keyId: string, serverId: string, signal?: AbortSignal): Promise<ApiKeyTool[]> => {
        return apiClient<ApiKeyTool[]>({
            url: `/auth/api-keys/${keyId}/servers/${serverId}/tools`,
            method: "GET",
            signal,
        });
    },
    /** Show (enabled) or hide a tool from this key's SEARCH_TOOLS and block running it. */
    setToolEnabled: async (keyId: string, serverId: string, toolName: string, enabled: boolean): Promise<ApiKeyToolVisibility> => {
        return apiClient<ApiKeyToolVisibility>({
            url: `/auth/api-keys/${keyId}/servers/${serverId}/tools/${encodeURIComponent(toolName)}`,
            method: "PATCH",
            data: { enabled },
        });
    },
};
