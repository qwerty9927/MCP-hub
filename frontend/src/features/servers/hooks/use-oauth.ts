import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { oauthApi } from "@/lib/api";
import { OAuthAuthorizationResponse, OAuthCompleteMessage, OAuthConnectRequest } from "@/types";
import { SERVERS_QUERY_KEY } from "./use-servers";

export const OAUTH_PROVIDERS_QUERY_KEY = ["oauth-providers"];

/** Message type posted by `/oauth/complete`; anything else on the window is ignored. */
export const OAUTH_MESSAGE_TYPE = "mcp-hub-oauth";

const POPUP_NAME = "mcp-hub-oauth";
const POPUP_FEATURES = "popup=yes,width=520,height=720";

export function useOAuthProviders(enabled = true) {
    return useQuery({
        queryKey: OAUTH_PROVIDERS_QUERY_KEY,
        queryFn: ({ signal }) => oauthApi.providers(signal),
        enabled,
    });
}

/**
 * - `starting`: the popup is open (blank) while the backend builds the authorization URL.
 * - `waiting`: the popup shows the provider's sign-in; the dialog waits for its message.
 * - `blocked`: the browser blocked the popup; the user can continue in this tab instead.
 */
export type OAuthFlowStatus = "idle" | "starting" | "waiting" | "blocked" | "success" | "error";

export interface OAuthFlowState {
    status: OAuthFlowStatus;
    authorizationUrl: string | null;
    serverId: string | null;
    error: string | null;
}

const IDLE: OAuthFlowState = { status: "idle", authorizationUrl: null, serverId: null, error: null };

function openPopup(url: string): Window | null {
    try {
        return window.open(url, POPUP_NAME, POPUP_FEATURES) ?? null;
    } catch {
        return null;
    }
}

function errorMessage(err: unknown): string {
    return err instanceof Error && err.message ? err.message : "Could not start the sign-in";
}

/** Friendly words for the error codes the callback can redirect with; unknown codes are shown as they are. */
export function describeOAuthError(code: string | null | undefined): string {
    switch (code) {
        case "access_denied":
            return "Access was declined on the provider's sign-in page.";
        case "state_expired":
        case "invalid_state":
            return "This sign-in expired or was already used. Start it again.";
        default:
            return code || "The provider returned an error.";
    }
}

/**
 * Runs an OAuth sign-in in a popup. The popup is opened synchronously in the click handler (so popup blockers
 * allow it) and pointed at the authorization URL once the backend returns it. `/oauth/complete` posts the
 * outcome back; only messages from this window's own origin are accepted.
 */
/** Everything that changes once a server is connected: lists, counts, provider badges. */
const connectedQueryKeys = () => [
    SERVERS_QUERY_KEY,
    OAUTH_PROVIDERS_QUERY_KEY,
    ["servers-summary"],
    ["system-metrics"],
    ["system-health"],
    ["tools"],
    ["tools-summary"],
];

export function useOAuthFlow() {
    const queryClient = useQueryClient();
    const [state, setState] = useState<OAuthFlowState>(IDLE);
    const popupRef = useRef<Window | null>(null);
    // Bumped on every start/reset so a late response from an abandoned run is ignored.
    const runRef = useRef(0);
    const activeRef = useRef(false);
    activeRef.current = state.status === "starting" || state.status === "waiting" || state.status === "blocked";

    useEffect(() => {
        const onMessage = (event: MessageEvent) => {
            if (event.origin !== window.location.origin) return;
            const data = event.data as Partial<OAuthCompleteMessage> | null;
            if (!data || typeof data !== "object" || data.type !== OAUTH_MESSAGE_TYPE) return;
            if (!activeRef.current) return;

            runRef.current += 1;
            popupRef.current = null;
            if (data.status === "success" && data.server_id) {
                for (const queryKey of connectedQueryKeys()) queryClient.invalidateQueries({ queryKey });
                setState({ ...IDLE, status: "success", serverId: data.server_id });
            } else {
                setState({ ...IDLE, status: "error", error: describeOAuthError(data.error) });
            }
        };
        window.addEventListener("message", onMessage);
        return () => window.removeEventListener("message", onMessage);
    }, [queryClient]);

    /** Call from a click handler. `request` asks the backend for the authorization URL. */
    const start = useCallback(
        async (request: () => Promise<OAuthAuthorizationResponse>) => {
            const run = ++runRef.current;
            const popup = openPopup("");
            popupRef.current = popup;
            setState({ ...IDLE, status: "starting" });

            try {
                const { authorization_url, server_id } = await request();
                if (run !== runRef.current) return;
                if (!authorization_url) {
                    // The server needed no sign-in: the backend already registered and connected it.
                    popup?.close();
                    popupRef.current = null;
                    if (!server_id) throw new Error("The server returned neither a sign-in URL nor a server");
                    for (const queryKey of connectedQueryKeys()) queryClient.invalidateQueries({ queryKey });
                    setState({ ...IDLE, status: "success", serverId: server_id });
                    return;
                }
                if (popup && !popup.closed) {
                    popup.location.href = authorization_url;
                    setState({ ...IDLE, status: "waiting", authorizationUrl: authorization_url });
                } else {
                    setState({ ...IDLE, status: "blocked", authorizationUrl: authorization_url });
                }
            } catch (err) {
                if (run !== runRef.current) return;
                popup?.close();
                popupRef.current = null;
                setState({ ...IDLE, status: "error", error: errorMessage(err) });
            }
        },
        [queryClient]
    );

    /** Opens the sign-in again (the user closed the popup, or it was blocked the first time). */
    const reopen = useCallback(() => {
        const url = state.authorizationUrl;
        if (!url) return;
        const popup = openPopup(url);
        popupRef.current = popup;
        popup?.focus?.();
        setState((prev) => ({ ...prev, status: popup ? "waiting" : "blocked" }));
    }, [state.authorizationUrl]);

    /** Full-page fallback when popups are blocked; `/oauth/complete` then redirects to the server. */
    const continueInTab = useCallback(() => {
        if (state.authorizationUrl) window.location.assign(state.authorizationUrl);
    }, [state.authorizationUrl]);

    const reset = useCallback(() => {
        runRef.current += 1;
        popupRef.current?.close();
        popupRef.current = null;
        setState(IDLE);
    }, []);

    /** Sign in to a catalog provider and create a new server. Call from a click handler. */
    const connect = useCallback((request: OAuthConnectRequest) => start(() => oauthApi.connect(request)), [start]);

    /** Sign in again for an existing OAuth server. Call from a click handler. */
    const reconnect = useCallback((serverId: string) => start(() => oauthApi.reconnect(serverId)), [start]);

    return { state, start, connect, reconnect, reopen, continueInTab, reset };
}
