import { BackendPendingId } from "@/lib/backend-pending";

export interface SettingsSection {
    label: string;
    href: string;
    /** Set when the section is a placeholder until the backend serves it. */
    pending?: BackendPendingId;
    /** Placeholder copy for pending sections. */
    description?: string;
}

export interface SettingsGroup {
    label: string;
    sections: SettingsSection[];
}

export const SETTINGS_GROUPS: SettingsGroup[] = [
    {
        label: "User settings",
        sections: [
            { label: "General", href: "/settings" },
            { label: "API Keys", href: "/settings/api-keys" },
            {
                label: "Notifications",
                href: "/settings/notifications",
                pending: "settings-notifications",
                description: "Choose which hub events reach you, such as a server going unhealthy or a sign-in expiring.",
            },
            {
                label: "Active Sessions",
                href: "/settings/active-sessions",
                pending: "settings-sessions",
                description: "See where you are signed in to the console and sign other sessions out.",
            },
        ],
    },
    {
        label: "Hub settings",
        sections: [
            { label: "System", href: "/settings/system" },
            {
                label: "Members",
                href: "/settings/members",
                pending: "settings-members",
                description: "Invite people to this hub and choose what each of them can change.",
            },
            {
                label: "Tool Policies",
                href: "/settings/tool-policies",
                pending: "settings-tool-policies",
                description: "Allow, block or require review for tools across every server.",
            },
            {
                label: "Rate Limits",
                href: "/settings/rate-limits",
                pending: "settings-rate-limits",
                description: "Cap how often each server or API key can call tools.",
            },
            {
                label: "Audit Logs",
                href: "/settings/audit-logs",
                pending: "settings-audit-logs",
                description: "Who changed what in the hub, and when.",
            },
            {
                label: "Webhooks",
                href: "/settings/webhooks",
                pending: "settings-webhooks",
                description: "Send hub events to your own endpoints.",
            },
        ],
    },
];

/** Pending sections by their URL slug (the last path segment). */
export const PENDING_SECTIONS: Record<string, SettingsSection & { pending: BackendPendingId }> = Object.fromEntries(
    SETTINGS_GROUPS.flatMap((group) => group.sections)
        .filter((section): section is SettingsSection & { pending: BackendPendingId } => Boolean(section.pending))
        .map((section) => [section.href.split("/").pop() as string, section])
);
