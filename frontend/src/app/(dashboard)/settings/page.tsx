"use client";

import React from "react";
import { useTheme } from "next-themes";
import { Server, Palette, CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuery } from "@tanstack/react-query";
import { systemApi } from "@/lib/api";
import { API_BASE_URL, SHOW_BACKEND_DETAILS } from "@/lib/config";
import { toast } from "sonner";
import { ApiKeysCard } from "@/features/auth/components/ApiKeysCard";

export default function SettingsPage() {
    const { theme, setTheme } = useTheme();

    // System readiness probe
    const {
        data: readiness,
        isLoading: readyLoading,
        refetch: refetchReady,
    } = useQuery({
        queryKey: ["settings-ready"],
        queryFn: ({ signal }) => systemApi.readiness(signal),
        enabled: SHOW_BACKEND_DETAILS,
    });

    // System health probe
    const {
        data: health,
        isLoading: healthLoading,
        refetch: refetchHealth,
    } = useQuery({
        queryKey: ["settings-health"],
        queryFn: ({ signal }) => systemApi.health(signal),
        enabled: SHOW_BACKEND_DETAILS,
    });

    const handleTestProbes = () => {
        refetchReady();
        refetchHealth();
        toast.success("Refreshed system probes");
    };

    return (
        <div className="max-w-4xl space-y-6">
            <PageHeader
                title="Settings & Telemetry"
                description={
                    SHOW_BACKEND_DETAILS
                        ? "Backend connection, API keys for MCP clients, and system probes."
                        : "API keys for MCP clients and appearance."
                }
            />

            {/* Backend API Configuration (hidden in production builds) */}
            {SHOW_BACKEND_DETAILS && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base flex items-center gap-2">
                            <Server className="h-4 w-4 text-primary" />
                            Backend Connection
                        </CardTitle>
                        <CardDescription>The REST API endpoint configured for all MCP hub management queries.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="api_url">API Base URL</Label>
                            <Input id="api_url" value={API_BASE_URL} readOnly className="font-mono text-sm bg-muted/40" />
                            <p className="text-xs text-muted-foreground">
                                Configured via <code className="font-mono text-xs">NEXT_PUBLIC_API_BASE_URL</code> in environment variables.
                            </p>
                        </div>

                        <div className="rounded-lg border border-border p-4 bg-muted/20 space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-sm font-semibold text-foreground">Live System Diagnostics</span>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleTestProbes}
                                    disabled={readyLoading || healthLoading}
                                    className="gap-1.5 h-8 text-xs"
                                >
                                    <RefreshCw className="h-3.5 w-3.5" />
                                    Refresh Probes
                                </Button>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                                <div className="flex items-center justify-between p-2.5 rounded bg-background border border-border">
                                    <span className="text-muted-foreground font-mono">GET /health</span>
                                    {healthLoading ? (
                                        <Skeleton className="h-5 w-20" />
                                    ) : health?.status === "ok" ? (
                                        <span className="inline-flex items-center gap-1 font-semibold text-emerald-600 dark:text-emerald-400">
                                            <CheckCircle2 className="h-3.5 w-3.5" />
                                            OK (v{health.version})
                                        </span>
                                    ) : (
                                        <span className="inline-flex items-center gap-1 font-semibold text-destructive">
                                            <XCircle className="h-3.5 w-3.5" />
                                            Unreachable
                                        </span>
                                    )}
                                </div>

                                <div className="flex items-center justify-between p-2.5 rounded bg-background border border-border">
                                    <span className="text-muted-foreground font-mono">GET /ready</span>
                                    {readyLoading ? (
                                        <Skeleton className="h-5 w-20" />
                                    ) : readiness?.status === "ready" ? (
                                        <span className="inline-flex items-center gap-1 font-semibold text-emerald-600 dark:text-emerald-400">
                                            <CheckCircle2 className="h-3.5 w-3.5" />
                                            Ready (checks passing)
                                        </span>
                                    ) : (
                                        <span className="inline-flex items-center gap-1 font-semibold text-destructive">
                                            <XCircle className="h-3.5 w-3.5" />
                                            Not Ready
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* MCP client credentials */}
            <ApiKeysCard />

            {/* Interface Theme */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        <Palette className="h-4 w-4 text-primary" />
                        Appearance
                    </CardTitle>
                    <CardDescription>Customize the dashboard color theme for your display preferences.</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center gap-3">
                        {["light", "dark", "system"].map((mode) => (
                            <Button
                                key={mode}
                                variant={theme === mode ? "default" : "outline"}
                                size="sm"
                                onClick={() => setTheme(mode)}
                                className="capitalize"
                            >
                                {mode}
                            </Button>
                        ))}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
