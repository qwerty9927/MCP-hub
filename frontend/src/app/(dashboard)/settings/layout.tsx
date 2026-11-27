import React from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { SettingsNav } from "@/features/settings/components/SettingsNav";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
    return (
        <div>
            <PageHeader title="Settings" description="Your profile and preferences, API keys for MCP clients, and hub configuration." />
            <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
                <SettingsNav className="lg:w-56 lg:shrink-0" />
                <div className="min-w-0 max-w-3xl flex-1">{children}</div>
            </div>
        </div>
    );
}
