"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Clock, Compass, Plus, RefreshCw, Server } from "lucide-react";
import { systemApi, serversApi, toolsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ListSkeleton } from "@/components/common/ListSkeleton";
import { StatCard } from "@/components/common/StatCard";
import { EmptyChart } from "@/components/common/EmptyChart";
import { ActionTile } from "@/components/common/ActionTile";
import { InfoCallout } from "@/components/common/InfoCallout";
import { SegmentedControl } from "@/components/common/SegmentedControl";
import { PendingBadge } from "@/components/common/PendingBackend";
import { RegisterServerButton } from "@/features/servers/components/RegisterServerButton";
import { RegisterServerDialog } from "@/features/servers/components/RegisterServerDialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useToolUsage } from "@/features/metrics/hooks/use-tool-usage";
import { useCallsTimeseries } from "@/features/metrics/hooks/use-calls-timeseries";
import { CallsTrendChart } from "@/features/metrics/components/CallsTrendChart";
import { describeDelta, formatPercent, summarizeToolUsage } from "@/features/metrics/utils";
import { useRecents } from "@/lib/recents";
import { cn, formatDuration } from "@/lib/utils";
import { ServerHealthStatus, ServerRead, UsageRange } from "@/types";

/** Tool-usage rows fetched for the analytics; the call total comes from the report itself. */
const USAGE_LIMIT = 50;
const SERVER_ROWS = 5;
const RECENT_ROWS = 5;

type RangeOption = Extract<UsageRange, "1h" | "24h" | "7d" | "30d">;

const RANGE_OPTIONS: { value: RangeOption; label: string }[] = [
    { value: "1h", label: "Last hour" },
    { value: "24h", label: "Last 24 hours" },
    { value: "7d", label: "Last 7 days" },
    { value: "30d", label: "Last 30 days" },
];

/** "↗ 12.4%" next to a value; growth in calls is shown, not judged, so only "up" gets a colour. */
export function DeltaChip({ current, previous }: { current: number; previous: number | null | undefined }) {
    const delta = describeDelta(current, previous);
    if (!delta) return null;
    const arrow = { up: "↗", down: "↘", flat: "→", new: "↗" }[delta.direction];
    const spoken = {
        up: `Up ${delta.label} from the previous period`,
        down: `Down ${delta.label} from the previous period`,
        flat: "No change from the previous period",
        new: "No calls in the previous period",
    }[delta.direction];
    return (
        <span
            aria-label={spoken}
            title={`Previous period: ${previous?.toLocaleString("en-US")} calls`}
            className={cn(
                "font-mono text-xs",
                delta.direction === "up" || delta.direction === "new" ? "text-success" : "text-muted-foreground"
            )}
        >
            <span aria-hidden="true">
                {arrow} {delta.label}
            </span>
        </span>
    );
}

const STATUS_TEXT: Record<string, { label: string; className: string }> = {
    HEALTHY: { label: "Healthy", className: "text-success" },
    UNHEALTHY: { label: "Unhealthy", className: "text-danger" },
    NEEDS_AUTH: { label: "Sign in again", className: "text-warning" },
    DISCONNECTED: { label: "Disconnected", className: "text-muted-foreground" },
};

export function statusText(status: ServerHealthStatus | string) {
    return STATUS_TEXT[status] ?? { label: "Unknown", className: "text-muted-foreground" };
}

/** Status dot; unhealthy is a square so it differs by shape and lightness, not hue alone. */
export function StatusDot({ status }: { status: ServerHealthStatus | string }) {
    return (
        <span
            aria-hidden="true"
            className={cn(
                "h-2 w-2 shrink-0",
                status === "HEALTHY" && "rounded-full bg-success-dot",
                status === "UNHEALTHY" && "rounded-sm bg-destructive ring-1 ring-danger",
                status === "NEEDS_AUTH" && "rounded-full bg-warning",
                !["HEALTHY", "UNHEALTHY", "NEEDS_AUTH"].includes(status) && "rounded-full bg-neutral-dot"
            )}
        />
    );
}

function formatCount(value: number): string {
    return value.toLocaleString("en-US");
}

export function OverviewDashboard() {
    const [range, setRange] = useState<RangeOption>("24h");
    const [registerOpen, setRegisterOpen] = useState(false);
    const [registerUsed, setRegisterUsed] = useState(false);
    const recents = useRecents();

    const {
        data: metrics,
        isLoading: metricsLoading,
        refetch: refetchMetrics,
    } = useQuery({
        queryKey: ["system-metrics"],
        queryFn: ({ signal }) => systemApi.metrics(signal),
        refetchInterval: 15000,
    });

    const { data: serversData, isLoading: serversLoading } = useQuery({
        queryKey: ["servers-summary"],
        queryFn: ({ signal }) => serversApi.list({ page: 1, page_size: 100 }, signal),
        refetchInterval: 15000,
    });

    const { data: toolsData, isLoading: toolsLoading } = useQuery({
        queryKey: ["tools-summary"],
        queryFn: ({ signal }) => toolsApi.list({ page: 1, page_size: 1 }, signal),
    });

    const { data: usage, isLoading: usageLoading, isFetching: usageFetching, refetch: refetchUsage } = useToolUsage(range, USAGE_LIMIT);
    const { data: trend, isLoading: trendLoading, refetch: refetchTrend } = useCallsTimeseries(range);
    const trendHasCalls = (trend?.buckets ?? []).some((bucket) => bucket.total_calls > 0);
    const summary = summarizeToolUsage(usage?.items ?? []);
    const totalCalls = usage?.total_calls ?? summary.totalCalls;
    const failingTools = summary.items.filter((item) => item.failed_calls > 0).sort((a, b) => b.failed_calls - a.failed_calls);

    const servers = serversData?.items ?? [];
    const totalServers = serversData?.total ?? metrics?.total_servers ?? servers.length;
    const healthyServers = metrics?.healthy_servers ?? servers.filter((s) => s.health_status === "HEALTHY").length;
    const unhealthyServers = servers.filter((s) => s.health_status === "UNHEALTHY").length;
    const attention = servers.filter((s) => s.health_status === "UNHEALTHY" || s.health_status === "NEEDS_AUTH");
    const totalTools = toolsData?.total ?? servers.reduce((acc, s) => acc + s.discovered_tool_count, 0);

    const openRegister = () => {
        setRegisterUsed(true);
        setRegisterOpen(true);
    };

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-6">
                {/* Servers */}
                <section aria-labelledby="overview-servers" className="flex flex-col gap-2">
                    <div className="flex items-center justify-between gap-2">
                        <Link
                            id="overview-servers"
                            href="/servers"
                            className="inline-flex items-center gap-1 text-[13px] font-medium text-foreground hover:text-primary"
                        >
                            Servers
                            <ChevronRight className="h-3 w-3" aria-hidden="true" />
                        </Link>
                        {!serversLoading && servers.length > 0 && (
                            <span className="text-xs text-muted-foreground">
                                {totalServers} registered
                                {unhealthyServers > 0 && (
                                    <>
                                        {" · "}
                                        <span className="text-danger">{unhealthyServers} unhealthy</span>
                                    </>
                                )}
                            </span>
                        )}
                    </div>
                    {serversLoading ? (
                        <ListSkeleton count={3} />
                    ) : servers.length === 0 ? (
                        <div className="flex flex-1 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border p-6 text-center">
                            <Server className="h-8 w-8 text-muted-foreground opacity-40" aria-hidden="true" />
                            <p className="text-sm text-muted-foreground">No MCP servers registered</p>
                            <RegisterServerButton size="sm" label="Register First Server" />
                        </div>
                    ) : (
                        servers.slice(0, SERVER_ROWS).map((server) => <ServerRow key={server.id} server={server} />)
                    )}
                </section>

                {/* Quick start */}
                <section aria-labelledby="overview-start" className="flex flex-col gap-2">
                    <h2 id="overview-start" className="text-[13px] font-medium leading-5">
                        Quick Start
                    </h2>
                    <ActionTile icon={Plus} label="Register a server" onClick={openRegister} />
                    <ActionTile icon={Compass} label="Browse discovery" href="/discovery" />
                </section>

                {/* Recents */}
                <section aria-labelledby="overview-recents" className="flex flex-col">
                    <h2 id="overview-recents" className="pb-2 text-[13px] font-medium leading-5">
                        Recents
                    </h2>
                    {recents.length === 0 ? (
                        <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                            Pages you open show here.
                        </p>
                    ) : (
                        recents.slice(0, RECENT_ROWS).map((recent) => (
                            <Link
                                key={recent.href}
                                href={recent.href}
                                className="flex min-h-11 items-center gap-2.5 border-b border-border px-2 text-[13px] text-foreground transition-colors hover:bg-accent"
                            >
                                <Clock className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                                <span className="min-w-0 flex-1 truncate">
                                    <span className="text-muted-foreground">{recent.section} / </span>
                                    <span className="font-medium">{recent.label}</span>
                                </span>
                                <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                            </Link>
                        ))
                    )}
                </section>
            </div>

            {/* Servers that need attention (real data), then the tool review queue (pending in the backend) */}
            {attention.length > 0 && (
                <InfoCallout
                    tone={attention.some((s) => s.health_status === "UNHEALTHY") ? "danger" : "warning"}
                    title={`${attention.length} ${attention.length === 1 ? "server needs" : "servers need"} attention`}
                    action={
                        <Button asChild variant="outline" size="sm" className="bg-card">
                            <Link href={`/servers/${attention[0].id}`}>Open {attention[0].name}</Link>
                        </Button>
                    }
                >
                    {attention.map((s, index) => (
                        <React.Fragment key={s.id}>
                            {index > 0 && " · "}
                            <span className="font-mono text-[13px]">{s.name}</span> {statusText(s.health_status).label.toLowerCase()}
                        </React.Fragment>
                    ))}
                </InfoCallout>
            )}
            <InfoCallout title="Review new tools before agents can call them" action={<PendingBadge id="new-tools-review" />}>
                Today every discovered tool is live as soon as a scan finds it. A review queue for newly discovered tools will show here.
            </InfoCallout>

            {/* Analytics */}
            <section aria-labelledby="overview-analytics" className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 id="overview-analytics" className="text-base font-semibold tracking-tight">
                        Analytics
                    </h2>
                    <div className="flex flex-wrap items-center gap-2">
                        <SegmentedControl label="Time range" value={range} onValueChange={setRange} options={RANGE_OPTIONS} />
                        <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Refresh analytics"
                            onClick={() => {
                                void refetchUsage();
                                void refetchTrend();
                                void refetchMetrics();
                            }}
                        >
                            <RefreshCw className={cn("h-4 w-4", usageFetching && "motion-safe:animate-spin")} aria-hidden="true" />
                        </Button>
                    </div>
                </div>

                <div className="grid grid-cols-[repeat(auto-fit,minmax(320px,1fr))] gap-4">
                    <StatCard
                        title="Tool Calls"
                        value={formatCount(totalCalls)}
                        loading={usageLoading}
                        valueAddon={<DeltaChip current={totalCalls} previous={usage?.previous_total_calls} />}
                        footnote={
                            <>
                                <span className="text-success">{formatCount(summary.completedCalls)} completed</span> ·{" "}
                                {formatCount(summary.failedCalls)} failed · {formatCount(summary.rejectedCalls)} rejected
                            </>
                        }
                    >
                        {trendLoading ? (
                            <Skeleton className="mt-2 h-36 w-full" />
                        ) : trend && trendHasCalls ? (
                            <CallsTrendChart buckets={trend.buckets} bucketSeconds={trend.bucket_seconds} />
                        ) : (
                            <EmptyChart label="No calls in this range" />
                        )}
                    </StatCard>

                    <StatCard
                        title="Failed Calls"
                        value={formatCount(summary.failedCalls)}
                        loading={usageLoading}
                        footnote={`${formatPercent(summary.failedCalls, totalCalls)} of calls in this range`}
                    >
                        {failingTools.length === 0 ? (
                            <EmptyChart label="No failures in this range" />
                        ) : (
                            <ul className="mt-2 flex flex-col divide-y divide-border">
                                {failingTools.slice(0, 4).map((item) => (
                                    <li key={`${item.server_id}:${item.tool_name}`} className="flex items-center gap-3 py-2 text-sm">
                                        <span className="min-w-0 flex-1 truncate font-mono text-[13px]">{item.tool_name}</span>
                                        <span className="truncate text-xs text-muted-foreground">{item.server_name}</span>
                                        <span className="font-mono text-xs text-danger">{formatCount(item.failed_calls)} failed</span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </StatCard>
                </div>

                <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
                    <StatCard
                        title="P90 Latency"
                        value={
                            usage?.p90_duration_ms === null || usage?.p90_duration_ms === undefined
                                ? "—"
                                : formatDuration(usage.p90_duration_ms)
                        }
                        loading={usageLoading}
                        footnote={`Avg ${summary.avgDurationMs === null ? "—" : formatDuration(summary.avgDurationMs)} · calls that reached a server`}
                    />
                    <StatCard
                        title="Rejected Calls"
                        value={formatCount(summary.rejectedCalls)}
                        loading={usageLoading}
                        footnote="Refused by the hub"
                    />
                    <StatCard
                        title="Active Connections"
                        value={formatCount(metrics?.active_sessions ?? 0)}
                        loading={metricsLoading}
                        footnote={`${healthyServers} healthy ${healthyServers === 1 ? "server" : "servers"}`}
                    />
                    <StatCard
                        title="Discovered Tools"
                        value={formatCount(totalTools)}
                        loading={toolsLoading || serversLoading}
                        footnote={`across ${totalServers} ${totalServers === 1 ? "server" : "servers"}`}
                    />
                </div>
            </section>

            {registerUsed && <RegisterServerDialog open={registerOpen} onOpenChange={setRegisterOpen} />}
        </div>
    );
}

function ServerRow({ server }: { server: ServerRead }) {
    const status = statusText(server.health_status);
    return (
        <Link
            href={`/servers/${server.id}`}
            className="flex items-center gap-3 rounded-lg border border-border bg-card p-3 text-foreground transition-colors hover:bg-accent"
        >
            <StatusDot status={server.health_status} />
            <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-sm font-semibold">{server.name}</span>
                <span className="font-mono text-xs text-muted-foreground">
                    {server.transport} · {server.discovered_tool_count} tools
                </span>
            </span>
            <span className={cn("text-xs font-medium", status.className)}>{status.label}</span>
        </Link>
    );
}
