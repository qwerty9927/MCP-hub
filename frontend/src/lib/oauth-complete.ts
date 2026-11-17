import { OAuthCompleteMessage } from "@/types";

/** Reads `?status=success&server_id=…` or `?status=error&error=…` from the callback redirect. */
export function readCompletionMessage(search: string): OAuthCompleteMessage {
    const params = new URLSearchParams(search);
    const status = params.get("status") === "success" ? "success" : "error";
    return {
        type: "mcp-hub-oauth",
        status,
        server_id: params.get("server_id"),
        error: status === "error" ? params.get("error") || "unknown_error" : null,
    };
}

/** Where the full-page flow (no popup) lands after the sign-in. */
export function completionRedirect(message: OAuthCompleteMessage): string {
    if (message.status === "success" && message.server_id) return `/servers/${encodeURIComponent(message.server_id)}`;
    return `/servers?oauth_error=${encodeURIComponent(message.error || "unknown_error")}`;
}
