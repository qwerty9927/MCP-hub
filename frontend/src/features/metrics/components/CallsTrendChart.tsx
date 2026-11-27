"use client";

import React from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CallBucket } from "@/types";
import { preferredTimeZone } from "@/lib/preferences";

/** Completed in the one brand hue; failed and rejected in their status colours, stacked on top. */
const SERIES = [
    { dataKey: "completed_calls", name: "Completed", color: "var(--trend-completed)" },
    { dataKey: "failed_calls", name: "Failed", color: "var(--trend-failed)" },
    { dataKey: "rejected_calls", name: "Rejected", color: "var(--trend-rejected)" },
] as const;

const COLOR_VARS =
    "[--trend-completed:hsl(var(--primary))] [--trend-failed:hsl(var(--danger-text))] [--trend-rejected:hsl(var(--rejected))]";

const AXIS_TICK = { fill: "hsl(var(--muted-foreground))", fontSize: 11 };
const DAY_SECONDS = 86_400;

interface CallsTrendChartProps {
    buckets: CallBucket[];
    bucketSeconds: number;
    height?: number;
}

/** Bucket start as a short label: time of day for sub-day buckets, the date otherwise. */
export function formatBucketStart(start: string, bucketSeconds: number, withDate = false): string {
    const date = new Date(start);
    const timeZone = preferredTimeZone();
    if (bucketSeconds >= DAY_SECONDS) {
        return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone }).format(date);
    }
    return new Intl.DateTimeFormat("en-US", {
        ...(withDate ? { month: "short", day: "numeric" } : {}),
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
        timeZone,
    }).format(date);
}

/** Tool calls per bucket, stacked by how they ended. */
export function CallsTrendChart({ buckets, bucketSeconds, height = 144 }: CallsTrendChartProps) {
    const total = buckets.reduce((sum, bucket) => sum + bucket.total_calls, 0);
    const peak = buckets.reduce<CallBucket | null>(
        (best, bucket) => (!best || bucket.total_calls > best.total_calls ? bucket : best),
        null
    );
    const summary =
        peak && peak.total_calls > 0
            ? `${total} calls over ${buckets.length} intervals; busiest ${formatBucketStart(peak.start, bucketSeconds, true)} with ${peak.total_calls}`
            : "No calls in this range";

    return (
        <div className={`${COLOR_VARS} mt-2`} role="img" aria-label={`Tool calls over time: ${summary}`} data-testid="calls-trend-chart">
            <ResponsiveContainer width="100%" height={height}>
                <BarChart data={buckets} margin={{ top: 4, right: 4, bottom: 0, left: -12 }} barCategoryGap="15%">
                    <CartesianGrid vertical={false} stroke="hsl(var(--border))" />
                    <XAxis
                        dataKey="start"
                        tick={AXIS_TICK}
                        axisLine={false}
                        tickLine={false}
                        minTickGap={32}
                        tickFormatter={(start: string) => formatBucketStart(start, bucketSeconds)}
                    />
                    <YAxis allowDecimals={false} width={40} tick={AXIS_TICK} axisLine={false} tickLine={false} />
                    <Tooltip
                        cursor={{ fill: "hsl(var(--muted))", opacity: 0.5 }}
                        content={({ active, payload }) => (
                            <TrendTooltip
                                active={active}
                                bucket={payload?.[0]?.payload as CallBucket | undefined}
                                bucketSeconds={bucketSeconds}
                            />
                        )}
                    />
                    {SERIES.map((series) => (
                        <Bar key={series.dataKey} dataKey={series.dataKey} name={series.name} stackId="calls" fill={series.color} />
                    ))}
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}

function TrendTooltip({ active, bucket, bucketSeconds }: { active?: boolean; bucket?: CallBucket; bucketSeconds: number }) {
    if (!active || !bucket) return null;
    return (
        <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
            <div className="mb-1 font-semibold">{formatBucketStart(bucket.start, bucketSeconds, true)}</div>
            <div className="font-mono">{bucket.total_calls} calls</div>
            {SERIES.map((series) => (
                <div key={series.dataKey} className="flex items-center gap-2 text-muted-foreground">
                    <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ background: series.color }} />
                    {series.name}: <span className="font-mono text-foreground">{bucket[series.dataKey]}</span>
                </div>
            ))}
        </div>
    );
}
