import { apiClient } from "../api-client";
import { OAuthAuthorizationResponse, OAuthConnectRequest, OAuthProvider } from "@/types";

export const oauthApi = {
    /** The hosted providers that can be connected with a sign-in, with availability and this user's connection count. */
    providers: async (signal?: AbortSignal): Promise<OAuthProvider[]> => {
        return apiClient<OAuthProvider[]>({
            url: "/oauth/providers",
            method: "GET",
            signal,
        });
    },

    /** Starts a sign-in for a new server; the returned URL is opened in the popup. */
    connect: async (payload: OAuthConnectRequest): Promise<OAuthAuthorizationResponse> => {
        return apiClient<OAuthAuthorizationResponse>({
            url: "/oauth/connect",
            method: "POST",
            data: payload,
        });
    },

    /** Starts a new sign-in for an existing OAuth server (for example after its tokens expired). */
    reconnect: async (serverId: string): Promise<OAuthAuthorizationResponse> => {
        return apiClient<OAuthAuthorizationResponse>({
            url: `/servers/${serverId}/oauth/reconnect`,
            method: "POST",
        });
    },
};
