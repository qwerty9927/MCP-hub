"use client";

import React from "react";
import { Server, CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuery } from "@tanstack/react-query";
import { systemApi } from "@/lib/api";
import { ReadyResponse } from "@/types";
import { API_BASE_URL, SHOW_BACKEND_DETAILS } from "@/lib/config";
import { toast } from "sonner";

/** "Not ready: database unreachable", naming each failing check of a `not_ready` probe. */
function notReadyLabel(readiness: ReadyResponse | undefined): string {
    const failing = Object.entries(readiness?.checks ?? {})
        .filter(([, passing]) => !passing)
        .map(([name]) => name);
    return failing.length > 0 ? `Not ready: ${failing.join(", ")} unreachable` : "Not Ready";
}

/** Settings › System: the backend connection and its live health/readiness probes. */
export default function SystemSettingsPage() {
    const {
        data: readiness,
        isLoading: readyLoading,
        isError: readyFailed,
        refetch: refetchReady,
    } = useQuery({
        queryKey: ["settings-ready"],
        queryFn: ({ signal }) => systemApi.readiness(signal),
    });

    const {
        data: health,
        isLoading: healthLoading,
        refetch: refetchHealth,
    } = useQuery({
        queryKey: ["settings-health"],
        queryFn: ({ signal }) => systemApi.health(signal),
    });

    const handleTestProbes = () => {
        refetchReady();
        refetchHealth();
        toast.success("Refreshed system probes");
    };

    return (
        <div className="flex flex-col gap-7">
            <div className="flex flex-col gap-1">
                <h2 className="text-xl font-bold tracking-tight">System</h2>
                <p className="text-sm text-muted-foreground">Live health and readiness of this hub&rsquo;s backend.</p>
            </div>

            {/* Backend connection and probes (production builds hide the API base URL and the version) */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Server className="h-4 w-4 text-primary" />
                        {SHOW_BACKEND_DETAILS ? "Backend Connection" : "System Status"}
                    </CardTitle>
                    <CardDescription>
                        {SHOW_BACKEND_DETAILS
                            ? "The REST API endpoint configured for all MCP hub management queries."
                            : "Live health and readiness of the MCP hub backend."}
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {SHOW_BACKEND_DETAILS && (
                        <div className="space-y-2">
                            <Label htmlFor="api_url">API Base URL</Label>
                            <Input id="api_url" value={API_BASE_URL} readOnly className="bg-muted/40 font-mono text-sm" />
                            <p className="text-xs text-muted-foreground">
                                Configured via <code className="font-mono text-xs">NEXT_PUBLIC_API_BASE_URL</code> in environment variables.
                            </p>
                        </div>
                    )}

                    <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-4">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-semibold text-foreground">Live System Diagnostics</span>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleTestProbes}
                                disabled={readyLoading || healthLoading}
                                className="h-8 gap-1.5 text-xs"
                            >
                                <RefreshCw className="h-3.5 w-3.5" />
                                Refresh Probes
                            </Button>
                        </div>

                        <div className="grid grid-cols-1 gap-3 text-xs sm:grid-cols-2">
                            <div className="flex items-center justify-between rounded border border-border bg-background p-2.5">
                                <span className="font-mono text-muted-foreground">GET /health</span>
                                {healthLoading ? (
                                    <Skeleton className="h-5 w-20" />
                                ) : health?.status === "ok" ? (
                                    <span className="inline-flex items-center gap-1 font-semibold text-success">
                                        <CheckCircle2 className="h-3.5 w-3.5" />
                                        {SHOW_BACKEND_DETAILS ? `OK (v${health.version})` : "OK"}
                                    </span>
                                ) : (
                                    <span className="inline-flex items-center gap-1 font-semibold text-danger">
                                        <XCircle className="h-3.5 w-3.5" />
                                        Unreachable
                                    </span>
                                )}
                            </div>

                            <div className="flex items-center justify-between rounded border border-border bg-background p-2.5">
                                <span className="font-mono text-muted-foreground">GET /ready</span>
                                {readyLoading ? (
                                    <Skeleton className="h-5 w-20" />
                                ) : !readyFailed && readiness?.status === "ready" ? (
                                    <span className="inline-flex items-center gap-1 font-semibold text-success">
                                        <CheckCircle2 className="h-3.5 w-3.5" />
                                        Ready (checks passing)
                                    </span>
                                ) : (
                                    <span className="inline-flex items-center gap-1 font-semibold text-danger">
                                        <XCircle className="h-3.5 w-3.5" />
                                        {readyFailed ? "Unreachable" : notReadyLabel(readiness)}
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
