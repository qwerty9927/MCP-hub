/**
 * UI the console already shows but the backend cannot serve yet. Each entry renders as a "Backend pending" badge
 * (see components/common/PendingBackend) and has a row in docs/backend-pending.md, the handoff for the API team.
 * Remove an entry, and its badge, once the backend ships what `needs` names.
 */
export interface BackendPendingItem {
    /** What the user would get. */
    title: string;
    /** The endpoint or field the UI waits for. */
    needs: string;
    /** Where the pending UI appears. */
    screens: string[];
}

export const BACKEND_PENDING = {
    "profile-display-name": {
        title: "Display name",
        needs: "display_name on users, PATCH /auth/me",
        screens: ["Settings › General"],
    },
    "profile-verified": {
        title: "Verified email",
        needs: "email_verified on GET /auth/me and a verification flow",
        screens: ["Settings › General"],
    },
    "auto-enable-readonly": {
        title: "Auto-enable read-only tools",
        needs: "tool annotations (readOnlyHint, destructiveHint) stored on tools, and a server-side user settings store",
        screens: ["Settings › General"],
    },
    "settings-sessions": {
        title: "Active console sessions",
        needs: "list and revoke console sign-ins (refresh-token families), e.g. GET /auth/sessions",
        screens: ["Settings › Active Sessions"],
    },
    "settings-tool-policies": {
        title: "Tool policies",
        needs: "hub-wide allow/deny and approval policies for tools",
        screens: ["Settings › Tool Policies"],
    },
} as const satisfies Record<string, BackendPendingItem>;

export type BackendPendingId = keyof typeof BACKEND_PENDING;
