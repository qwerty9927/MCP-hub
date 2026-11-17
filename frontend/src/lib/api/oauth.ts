import { apiClient } from "../api-client";
import { OAuthAuthorizationResponse, OAuthConnectRequest, OAuthProvider } from "@/types";

/**
 * Starting a sign-in runs discovery and client registration with the provider first; the backend gives that up to
 * 40 s (START_TIMEOUT_SECONDS in backend/app/services/oauth_service.py). Wait a little longer than it, so the backend's
 * own answer (a URL or a clear error) reaches the dialog instead of a generic client timeout.
 */
export const OAUTH_START_TIMEOUT_MS = 45_000;

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
            timeout: OAUTH_START_TIMEOUT_MS,
        });
    },

    /** Starts a new sign-in for an existing OAuth server (for example after its tokens expired). */
    reconnect: async (serverId: string): Promise<OAuthAuthorizationResponse> => {
        return apiClient<OAuthAuthorizationResponse>({
            url: `/servers/${serverId}/oauth/reconnect`,
            method: "POST",
            timeout: OAUTH_START_TIMEOUT_MS,
        });
    },
};
