"use client";

import React from "react";
import Link from "next/link";
import { Server, Wrench, Activity, History, CheckCircle2, XCircle, Clock, Radio, ExternalLink, Plus, Play } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { systemApi, serversApi, executionsApi, toolsApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { HealthBadge } from "@/components/common/HealthBadge";
import { Skeleton } from "@/components/ui/skeleton";
import { ListSkeleton } from "@/components/common/ListSkeleton";
import { formatDate, formatDuration } from "@/lib/utils";

export function OverviewDashboard() {
    // 1. System Metrics Telemetry
    const { data: metrics, isLoading: metricsLoading } = useQuery({
        queryKey: ["system-metrics"],
        queryFn: ({ signal }) => systemApi.metrics(signal),
        refetchInterval: 15000,
    });

    // 2. Servers summary
    const { data: serversData, isLoading: serversLoading } = useQuery({
        queryKey: ["servers-summary"],
        queryFn: ({ signal }) => serversApi.list({ page: 1, page_size: 100 }, signal),
        refetchInterval: 15000,
    });

    // 3. Tools summary
    const { data: toolsData, isLoading: toolsLoading } = useQuery({
        queryKey: ["tools-summary"],
        queryFn: ({ signal }) => toolsApi.list({ page: 1, page_size: 1 }, signal),
    });

    // 4. Recent Executions
    const { data: executionsData, isLoading: executionsLoading } = useQuery({
        queryKey: ["recent-executions"],
        queryFn: ({ signal }) => executionsApi.list({ page: 1, page_size: 8 }, signal),
        refetchInterval: 15000,
    });

    const servers = serversData?.items || [];
    const executions = executionsData?.items || [];

    const totalServers = metrics?.total_servers ?? servers.length;
    const enabledServers = servers.filter((s) => s.enabled).length;
    const healthyServers = metrics?.healthy_servers ?? servers.filter((s) => s.health_status === "HEALTHY").length;
    const unhealthyServers = servers.filter((s) => s.health_status === "UNHEALTHY").length;

    const totalTools = toolsData?.total ?? servers.reduce((acc, s) => acc + s.discovered_tool_count, 0);

    // Execution stats from recent runs
    const totalRecent = executions.length;
    const failedRecent = executions.filter((e) => e.is_error).length;
    const successRecent = totalRecent - failedRecent;
    const avgDuration = totalRecent > 0 ? executions.reduce((acc, e) => acc + e.duration_ms, 0) / totalRecent : 0;

    // Active sessions
    const activeSessions = metrics?.active_sessions ?? 0;

    return (
        <div className="space-y-6">
            {/* Metric Cards Banner */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Total Servers */}
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Servers</CardTitle>
                        <Server className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        {serversLoading || metricsLoading ? (
                            <Skeleton className="h-8 w-16" />
                        ) : (
                            <>
                                <div className="text-2xl font-bold font-mono">{totalServers}</div>
                                <p className="text-xs text-muted-foreground mt-1">
                                    <span className="text-emerald-600 dark:text-emerald-400 font-medium">{enabledServers} enabled</span>
                                    {" · "}
                                    <span>{healthyServers} healthy</span>
                                    {unhealthyServers > 0 && (
                                        <span className="text-destructive font-medium ml-1">({unhealthyServers} unhealthy)</span>
                                    )}
                                </p>
                            </>
                        )}
                    </CardContent>
                </Card>

                {/* Total Tools */}
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Discovered Tools</CardTitle>
                        <Wrench className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        {toolsLoading || serversLoading ? (
                            <Skeleton className="h-8 w-16" />
                        ) : (
                            <>
                                <div className="text-2xl font-bold font-mono">{totalTools}</div>
                                <p className="text-xs text-muted-foreground mt-1">Across all active MCP server sessions</p>
                            </>
                        )}
                    </CardContent>
                </Card>

                {/* Active Sessions */}
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Active Sessions</CardTitle>
                        <Radio className="h-4 w-4 text-emerald-500 animate-pulse" />
                    </CardHeader>
                    <CardContent>
                        {metricsLoading ? (
                            <Skeleton className="h-8 w-16" />
                        ) : (
                            <>
                                <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">{activeSessions}</div>
                                <p className="text-xs text-muted-foreground mt-1">Live connection managers active</p>
                            </>
                        )}
                    </CardContent>
                </Card>

                {/* Total Executions & Latency */}
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Executions</CardTitle>
                        <Activity className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        {metricsLoading ? (
                            <Skeleton className="h-8 w-16" />
                        ) : (
                            <>
                                <div className="text-2xl font-bold font-mono">
                                    {metrics?.total_executions ?? executionsData?.total ?? 0}
                                </div>
                                <p className="text-xs text-muted-foreground mt-1">
                                    Avg latency:{" "}
                                    <span className="font-mono font-medium text-foreground">{formatDuration(avgDuration)}</span>
                                </p>
                            </>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Middle Grid: Servers Overview + Recent Executions */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Registered Servers Quick View */}
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between">
                        <div>
                            <CardTitle className="text-base flex items-center gap-2">
                                <Server className="h-4 w-4 text-primary" />
                                MCP Servers Status
                            </CardTitle>
                            <CardDescription>Overview of registered server health and transport connectivity.</CardDescription>
                        </div>
                        <Button asChild size="sm" variant="outline" className="h-8 text-xs gap-1">
                            <Link href="/servers">
                                View All
                                <ExternalLink className="h-3 w-3" />
                            </Link>
                        </Button>
                    </CardHeader>
                    <CardContent>
                        {serversLoading ? (
                            <ListSkeleton count={4} />
                        ) : servers.length === 0 ? (
                            <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
                                <Server className="h-8 w-8 opacity-40 mb-2" />
                                <p className="text-sm">No MCP servers registered</p>
                                <Button asChild size="sm" className="mt-3 gap-1.5">
                                    <Link href="/servers/new">
                                        <Plus className="h-3.5 w-3.5" />
                                        Register First Server
                                    </Link>
                                </Button>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {servers.slice(0, 5).map((server) => (
                                    <div
                                        key={server.id}
                                        className="flex items-center justify-between rounded-lg border border-border p-3 transition-colors hover:bg-muted/40"
                                    >
                                        <div className="flex flex-col min-w-0 pr-3">
                                            <Link href={`/servers/${server.id}`} className="font-semibold text-sm hover:underline truncate">
                                                {server.name}
                                            </Link>
                                            <span className="text-xs text-muted-foreground font-mono">
                                                {server.transport} · {server.discovered_tool_count} tools
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-2 shrink-0">
                                            <HealthBadge status={server.health_status} />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Recent Invocations */}
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between">
                        <div>
                            <CardTitle className="text-base flex items-center gap-2">
                                <History className="h-4 w-4 text-primary" />
                                Recent Executions
                            </CardTitle>
                            <CardDescription>Real-time tool invocation logs and error diagnostics.</CardDescription>
                        </div>
                        <Button asChild size="sm" variant="outline" className="h-8 text-xs gap-1">
                            <Link href="/executions">
                                View All
                                <ExternalLink className="h-3 w-3" />
                            </Link>
                        </Button>
                    </CardHeader>
                    <CardContent>
                        {executionsLoading ? (
                            <ListSkeleton count={4} />
                        ) : executions.length === 0 ? (
                            <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
                                <Play className="h-8 w-8 opacity-40 mb-2" />
                                <p className="text-sm">No tool executions recorded</p>
                                <Button asChild size="sm" className="mt-3 gap-1.5">
                                    <Link href="/playground">
                                        <Play className="h-3.5 w-3.5" />
                                        Open Tool Playground
                                    </Link>
                                </Button>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {executions.map((exec) => (
                                    <div
                                        key={exec.id}
                                        className="flex items-center justify-between rounded-lg border border-border p-3 transition-colors hover:bg-muted/40"
                                    >
                                        <div className="flex flex-col min-w-0 pr-3">
                                            <Link
                                                href={`/executions/${exec.id}`}
                                                className="font-mono text-sm font-semibold hover:underline truncate"
                                            >
                                                {exec.tool_name}
                                            </Link>
                                            <span className="text-xs text-muted-foreground truncate">
                                                {exec.server_name} · {formatDate(exec.executed_at)}
                                            </span>
                                        </div>

                                        <div className="flex items-center gap-2 shrink-0">
                                            <span className="text-xs font-mono text-muted-foreground">
                                                {formatDuration(exec.duration_ms)}
                                            </span>
                                            {exec.is_error ? (
                                                <Badge variant="destructive" className="h-6 px-1.5 text-xs">
                                                    <XCircle className="h-3 w-3 mr-1" />
                                                    Failed
                                                </Badge>
                                            ) : (
                                                <Badge variant="success" className="h-6 px-1.5 text-xs">
                                                    <CheckCircle2 className="h-3 w-3 mr-1" />
                                                    Success
                                                </Badge>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
