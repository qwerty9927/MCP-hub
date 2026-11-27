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
    "new-tools-review": {
        title: "Newly discovered tools to review",
        needs: "stable tool ids across refresh, first_seen_at and a review status on tools, plus an approve endpoint",
        screens: ["Overview callout", "Server callout"],
    },
    "server-rate-limit": {
        title: "Calls against a rate limit",
        needs: "per-server rate limit config and usage, e.g. GET /servers/{id}/quota",
        screens: ["Server › Usage by tool"],
    },
    "hub-switcher": {
        title: "Switch between hub instances",
        needs: "workspaces / hub instances model and a list endpoint",
        screens: ["Sidebar"],
    },
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
    "profile-delete": {
        title: "Delete profile",
        needs: "DELETE /auth/me",
        screens: ["Settings › General"],
    },
    "auto-enable-readonly": {
        title: "Auto-enable read-only tools",
        needs: "tool annotations (readOnlyHint, destructiveHint) stored on tools, and a server-side user settings store",
        screens: ["Settings › General"],
    },
    "settings-notifications": {
        title: "Notifications",
        needs: "notification preferences and delivery (e.g. GET/PUT /settings/notifications)",
        screens: ["Settings › Notifications"],
    },
    "settings-sessions": {
        title: "Active console sessions",
        needs: "list and revoke console sign-ins (refresh-token families), e.g. GET /auth/sessions",
        screens: ["Settings › Active Sessions"],
    },
    "settings-members": {
        title: "Members",
        needs: "members and roles on a shared hub",
        screens: ["Settings › Members"],
    },
    "settings-tool-policies": {
        title: "Tool policies",
        needs: "hub-wide allow/deny and approval policies for tools",
        screens: ["Settings › Tool Policies"],
    },
    "settings-rate-limits": {
        title: "Rate limits",
        needs: "configurable per-server / per-key rate limits",
        screens: ["Settings › Rate Limits"],
    },
    "settings-audit-logs": {
        title: "Audit logs",
        needs: "an audit log table and GET /audit-logs",
        screens: ["Settings › Audit Logs"],
    },
    "settings-webhooks": {
        title: "Webhooks",
        needs: "webhook subscriptions and delivery",
        screens: ["Settings › Webhooks"],
    },
    "remote-catalog": {
        title: "Remote MCP catalog (e.g. Cloudflare)",
        needs: "a catalog of remote MCP servers beyond the static OAuth providers list",
        screens: ["Discovery"],
    },
} as const satisfies Record<string, BackendPendingItem>;

export type BackendPendingId = keyof typeof BACKEND_PENDING;
