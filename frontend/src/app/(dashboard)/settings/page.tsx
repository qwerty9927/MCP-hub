"use client";

import React, { useMemo } from "react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { PendingBadge, PendingFeature } from "@/components/common/PendingBackend";
import { SettingsGroup, SettingsRow } from "@/features/settings/components/SettingsRow";
import { useMe } from "@/features/auth/hooks/use-auth";
import { usePreferences } from "@/lib/use-preferences";

const BROWSER_ZONE = "browser";

const FALLBACK_ZONES = [
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Los_Angeles",
    "Europe/London",
    "Europe/Berlin",
    "Asia/Ho_Chi_Minh",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Australia/Sydney",
];

function timeZones(): string[] {
    const supported = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf;
    try {
        return supported ? ["UTC", ...supported("timeZone").filter((zone) => zone !== "UTC")] : FALLBACK_ZONES;
    } catch {
        return FALLBACK_ZONES;
    }
}

function browserZone(): string {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch {
        return "UTC";
    }
}

/** Settings › General: profile, preferences, features and the danger zone. */
export default function GeneralSettingsPage() {
    const { data: me, isLoading } = useMe();
    const { theme, setTheme } = useTheme();
    const [preferences, setPreferences] = usePreferences();
    const zones = useMemo(timeZones, []);

    const memberSince = me?.created_at ? new Intl.DateTimeFormat("en-US", { dateStyle: "long" }).format(new Date(me.created_at)) : null;

    return (
        <div className="flex flex-col gap-7">
            <div className="flex flex-col gap-1">
                <h2 className="text-xl font-bold tracking-tight">General</h2>
                {isLoading ? (
                    <Skeleton className="h-5 w-64" />
                ) : (
                    <p className="text-sm text-muted-foreground">
                        {me?.email}
                        {memberSince && ` · Member since ${memberSince}`}
                    </p>
                )}
            </div>

            <SettingsGroup title="Profile">
                <SettingsRow label="Display name">
                    <PendingFeature id="profile-display-name">
                        <Button variant="outline" size="sm" tabIndex={-1}>
                            Set Display Name
                        </Button>
                    </PendingFeature>
                </SettingsRow>
                <SettingsRow label="Email">
                    <span className="font-mono text-[13px] text-muted-foreground">{me?.email ?? "—"}</span>
                    <PendingBadge id="profile-verified" />
                </SettingsRow>
            </SettingsGroup>

            <SettingsGroup title="Preferences">
                <SettingsRow label="Appearance" htmlFor="appearance">
                    <Select value={theme ?? "dark"} onValueChange={setTheme}>
                        <SelectTrigger id="appearance" className="h-8 w-[140px] text-[13px]">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="dark">Dark</SelectItem>
                            <SelectItem value="light">Light</SelectItem>
                            <SelectItem value="system">System</SelectItem>
                        </SelectContent>
                    </Select>
                </SettingsRow>
                <SettingsRow label="Timezone" htmlFor="timezone" description="Used for every date in the console. Saved in this browser.">
                    <Select
                        value={preferences.timeZone ?? BROWSER_ZONE}
                        onValueChange={(value) => setPreferences({ timeZone: value === BROWSER_ZONE ? null : value })}
                    >
                        <SelectTrigger id="timezone" className="h-8 w-[220px] font-mono text-[13px]">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value={BROWSER_ZONE}>Browser ({browserZone()})</SelectItem>
                            {zones.map((zone) => (
                                <SelectItem key={zone} value={zone} className="font-mono">
                                    {zone}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </SettingsRow>
            </SettingsGroup>

            <SettingsGroup title="Features">
                <SettingsRow
                    label="Keyboard shortcuts"
                    htmlFor="keyboard-shortcuts"
                    description="⌘K / Ctrl+K opens quick search from any page. Saved in this browser."
                >
                    <Switch
                        id="keyboard-shortcuts"
                        checked={preferences.keyboardShortcuts}
                        onCheckedChange={(checked) => setPreferences({ keyboardShortcuts: checked })}
                    />
                </SettingsRow>
                <SettingsRow
                    label="Auto-enable read-only tools"
                    description="Newly discovered tools that declare readOnlyHint skip review and go live at once."
                >
                    <PendingFeature id="auto-enable-readonly">
                        <Switch aria-label="Auto-enable read-only tools" checked={false} tabIndex={-1} />
                    </PendingFeature>
                </SettingsRow>
            </SettingsGroup>
        </div>
    );
}
