"use client";

import React, { useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { SegmentedControl } from "@/components/common/SegmentedControl";
import { PendingBadge } from "@/components/common/PendingBackend";
import { useToolUsage } from "@/features/metrics/hooks/use-tool-usage";
import { summarizeToolUsage } from "@/features/metrics/utils";
import { formatDuration } from "@/lib/utils";
import { ToolUsage, UsageRange } from "@/types";

/** The report is limited to this server, so 50 rows cover all but the largest servers. */
const USAGE_LIMIT = 50;
const TOP_TOOLS = 5;

type Metric = "calls" | "latency";

const RANGES: { value: UsageRange; label: string }[] = [
    { value: "1h", label: "Last hour" },
    { value: "24h", label: "Last 24 hours" },
    { value: "7d", label: "Last 7 days" },
    { value: "30d", label: "Last 30 days" },
    { value: "all", label: "All time" },
];

function formatCount(value: number): string {
    return value.toLocaleString("en-US");
}

/** P90 latency of a tool, falling back to its average for reports without percentiles. */
function latencyOf(item: ToolUsage): number | null {
    return item.p90_duration_ms ?? item.avg_duration_ms ?? null;
}

/** "Usage by tool" for one server: calls or P90 latency per tool, and which tools fail. */
export function ServerUsageCard({ serverId }: { serverId: string }) {
    const [range, setRange] = useState<UsageRange>("24h");
    const [metric, setMetric] = useState<Metric>("calls");
    const { data, isLoading } = useToolUsage(range, USAGE_LIMIT, serverId);
    const summary = summarizeToolUsage(data?.items ?? [], serverId);
    const totalCalls = data?.total_calls ?? summary.totalCalls;
    const p90 = data?.p90_duration_ms ?? null;

    const ranked =
        metric === "calls"
            ? [...summary.items].sort((a, b) => b.total_calls - a.total_calls)
            : summary.items.filter((item) => latencyOf(item) !== null).sort((a, b) => (latencyOf(b) ?? 0) - (latencyOf(a) ?? 0));
    const top = ranked.slice(0, TOP_TOOLS);
    const max = top.length > 0 ? (metric === "calls" ? top[0].total_calls : (latencyOf(top[0]) ?? 0)) : 0;
    const errors = summary.items
        .filter((item) => item.failed_calls + item.rejected_calls > 0)
        .sort((a, b) => b.failed_calls + b.rejected_calls - (a.failed_calls + a.rejected_calls));
    const rangeLabel = RANGES.find((option) => option.value === range)?.label.toLowerCase() ?? "";

    return (
        <section
            aria-labelledby="server-usage"
            className="overflow-hidden rounded-xl border border-border bg-card shadow-[0_1px_3px_0_rgba(0,0,0,0.1),0_1px_2px_-1px_rgba(0,0,0,0.1)]"
        >
            <h2 id="server-usage" className="border-b border-border bg-muted px-5 py-3 text-sm font-semibold">
                Usage by tool
            </h2>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
                <div className="flex flex-col gap-0.5">
                    <span className="flex flex-wrap items-center gap-2 text-[13px]">
                        Calls, {rangeLabel}:<span className="font-mono font-semibold">{isLoading ? "…" : formatCount(totalCalls)}</span>
                        <PendingBadge id="server-rate-limit" />
                    </span>
                    <span className="text-xs text-muted-foreground">Tools appear here after their first call through the hub.</span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <SegmentedControl
                        label="Metric"
                        value={metric}
                        onValueChange={setMetric}
                        options={[
                            { value: "calls", label: "Calls" },
                            { value: "latency", label: "Latency" },
                        ]}
                    />
                    <Select value={range} onValueChange={(value) => setRange(value as UsageRange)}>
                        <SelectTrigger aria-label="Time range" className="h-9 w-[150px] text-[13px]">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {RANGES.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {/* gap-px over a border-coloured grid draws the divider whether the panes sit side by side or stack */}
            <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-px bg-border">
                {/* Errors */}
                <div className="flex min-h-[240px] flex-col gap-3 bg-card px-5 py-4">
                    <div className="flex items-center justify-between">
                        <h3 className="text-[13px] font-medium">Errors</h3>
                        <span className="rounded-full bg-muted px-2 font-mono text-xs leading-5 text-muted-foreground">
                            Failed: {formatCount(summary.failedCalls)} · Rejected: {formatCount(summary.rejectedCalls)}
                        </span>
                    </div>
                    {isLoading ? (
                        <Skeleton className="h-24 w-full" />
                    ) : errors.length === 0 ? (
                        <div className="flex flex-1 flex-col items-center justify-center gap-1 text-center">
                            <span className="text-[13px] font-medium">No errors in this time range</span>
                            <span className="text-xs text-muted-foreground">Try another metric or time range to find activity.</span>
                        </div>
                    ) : (
                        <ul className="flex flex-col divide-y divide-border">
                            {errors.slice(0, TOP_TOOLS).map((item) => (
                                <li key={item.tool_name} className="flex items-center gap-3 py-2">
                                    <span className="min-w-0 flex-1 truncate font-mono text-xs">{item.tool_name}</span>
                                    {item.failed_calls > 0 && (
                                        <span className="font-mono text-xs text-danger">{formatCount(item.failed_calls)} failed</span>
                                    )}
                                    {item.rejected_calls > 0 && (
                                        <span className="font-mono text-xs text-rejected">{formatCount(item.rejected_calls)} rejected</span>
                                    )}
                                </li>
                            ))}
                        </ul>
                    )}
                </div>

                {/* Top tools */}
                <div className="flex min-h-[240px] flex-col gap-3.5 bg-card px-5 py-4">
                    <div className="flex items-center justify-between gap-2">
                        <h3 className="text-[13px] font-medium">Top Tools</h3>
                        {metric === "calls" ? (
                            <span className="rounded-full bg-muted px-2 font-mono text-xs leading-5 text-muted-foreground">
                                Calls: {formatCount(totalCalls)}
                            </span>
                        ) : (
                            <span className="rounded-full bg-muted px-2 font-mono text-xs leading-5 text-muted-foreground">
                                P90: {p90 === null ? "—" : formatDuration(p90)} · Avg:{" "}
                                {summary.avgDurationMs === null ? "—" : formatDuration(summary.avgDurationMs)}
                            </span>
                        )}
                    </div>
                    {isLoading ? (
                        <Skeleton className="h-24 w-full" />
                    ) : top.length === 0 ? (
                        <div className="flex flex-1 items-center justify-center text-center text-[13px] text-muted-foreground">
                            No calls to this server in this time range
                        </div>
                    ) : (
                        <ul className="flex flex-col gap-3.5">
                            {top.map((item) => {
                                const value = metric === "calls" ? item.total_calls : (latencyOf(item) ?? 0);
                                const width = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0;
                                return (
                                    <li key={item.tool_name} className="flex flex-col gap-1.5">
                                        <div className="flex justify-between gap-2 font-mono text-xs">
                                            <span className="truncate">{item.tool_name}</span>
                                            <span className="shrink-0 text-muted-foreground">
                                                {metric === "calls"
                                                    ? `${formatCount(item.total_calls)} calls`
                                                    : `${formatDuration(value)} p90`}
                                            </span>
                                        </div>
                                        <div className="h-2 rounded-full bg-muted" aria-hidden="true">
                                            <div className="h-2 rounded-full bg-primary" style={{ width: `${width}%` }} />
                                        </div>
                                    </li>
                                );
                            })}
                        </ul>
                    )}
                </div>
            </div>
        </section>
    );
}
