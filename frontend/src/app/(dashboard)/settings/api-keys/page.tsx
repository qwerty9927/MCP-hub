import React from "react";
import { ApiKeysCard } from "@/features/auth/components/ApiKeysCard";

/** Settings › API Keys: keys MCP clients use to reach the hub's /mcp endpoint. */
export default function ApiKeysSettingsPage() {
    return (
        <div className="flex flex-col gap-7">
            <div className="flex flex-col gap-1">
                <h2 className="text-xl font-bold tracking-tight">API Keys</h2>
                <p className="text-sm text-muted-foreground">Keys MCP clients and agents use to connect to this hub.</p>
            </div>
            <ApiKeysCard />
        </div>
    );
}
