"use client";

import React, { useState } from "react";
import { useTheme } from "next-themes";
import {
    Settings as SettingsIcon,
    Server,
    Shield,
    Palette,
    CheckCircle2,
    XCircle,
    RefreshCw,
    Info,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuery } from "@tanstack/react-query";
import { systemApi } from "@/lib/api";
import { toast } from "sonner";

export default function SettingsPage() {
    const { theme, setTheme } = useTheme();

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

    // System readiness probe
    const {
        data: readiness,
        isLoading: readyLoading,
        refetch: refetchReady,
    } = useQuery({
        queryKey: ["settings-ready"],
        queryFn: ({ signal }) => systemApi.readiness(signal),
    });

    // System health probe
    const {
        data: health,
        isLoading: healthLoading,
        refetch: refetchHealth,
    } = useQuery({
        queryKey: ["settings-health"],
        queryFn: ({ signal }) => systemApi.health(signal),
    });

    const [authToken, setAuthToken] = useState<string>(() => {
        if (typeof window !== "undefined") {
            return sessionStorage.getItem("mcp_auth_token") || "";
        }
        return "";
    });

    const handleSaveToken = () => {
        if (typeof window !== "undefined") {
            if (authToken.trim()) {
                sessionStorage.setItem("mcp_auth_token", authToken.trim());
                toast.success("Authentication token saved for active browser session");
            } else {
                sessionStorage.removeItem("mcp_auth_token");
                toast.info("Session authentication token removed");
            }
        }
    };

    const handleTestProbes = () => {
        refetchReady();
        refetchHealth();
        toast.success("Refreshed system probes");
    };

    return (
        <div className="max-w-4xl space-y-6">
            <PageHeader
                title="Settings & Telemetry"
                description="Configure backend connection endpoints, authentication credentials, and view system probes."
            />

            {/* Backend API Configuration */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        <Server className="h-4 w-4 text-primary" />
                        Backend Connection
                    </CardTitle>
                    <CardDescription>
                        The REST API endpoint configured for all MCP hub management queries.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="api_url">API Base URL</Label>
                        <Input
                            id="api_url"
                            value={apiBaseUrl}
                            readOnly
                            className="font-mono text-sm bg-muted/40"
                        />
                        <p className="text-xs text-muted-foreground">
                            Configured via{" "}
                            <code className="font-mono text-xs">NEXT_PUBLIC_API_BASE_URL</code> in
                            environment variables.
                        </p>
                    </div>

                    <div className="rounded-lg border border-border p-4 bg-muted/20 space-y-3">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-semibold text-foreground">
                                Live System Diagnostics
                            </span>
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

            {/* Security & Authentication */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        <Shield className="h-4 w-4 text-emerald-500" />
                        Authentication Integration
                    </CardTitle>
                    <CardDescription>
                        Optional session token attached as a Bearer token in request headers.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="token">Session Authorization Token</Label>
                        <Input
                            id="token"
                            type="password"
                            placeholder="e.g. Bearer token for protected gateway"
                            value={authToken}
                            onChange={(e) => setAuthToken(e.target.value)}
                            className="font-mono text-xs"
                        />
                        <p className="text-xs text-muted-foreground">
                            Stored only in volatile session storage for the current browser session.
                            Never written to disk or logs.
                        </p>
                    </div>

                    <div className="flex justify-end">
                        <Button size="sm" onClick={handleSaveToken}>
                            Save Token
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Interface Theme */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        <Palette className="h-4 w-4 text-primary" />
                        Appearance
                    </CardTitle>
                    <CardDescription>
                        Customize the dashboard color theme for your display preferences.
                    </CardDescription>
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
