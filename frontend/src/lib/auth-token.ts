/**
 * Console login token storage.
 * Kept in sessionStorage (per tab, cleared when the tab closes); the Axios interceptor attaches it.
 */
export const AUTH_TOKEN_KEY = "mcp_auth_token";
export const AUTH_CHANGED_EVENT = "mcp-auth-changed";

export function getAuthToken(): string | null {
    if (typeof window === "undefined") return null;
    try {
        return sessionStorage.getItem(AUTH_TOKEN_KEY);
    } catch {
        return null;
    }
}

export function setAuthToken(token: string): void {
    if (typeof window === "undefined") return;
    sessionStorage.setItem(AUTH_TOKEN_KEY, token);
    window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

export function clearAuthToken(): void {
    if (typeof window === "undefined") return;
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
    window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

/** Where to send a signed-out user, remembering the page they were on. */
export function loginPath(next?: string): string {
    if (!next || next.startsWith("/login") || next.startsWith("/register")) return "/login";
    return `/login?next=${encodeURIComponent(next)}`;
}

/** Only same-site paths are accepted as a post-login destination. */
export function safeNextPath(next: string | null | undefined): string {
    if (!next || !next.startsWith("/") || next.startsWith("//")) return "/overview";
    return next;
}
