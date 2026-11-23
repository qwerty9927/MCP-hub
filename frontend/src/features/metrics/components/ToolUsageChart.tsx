"use client";

import React from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ToolUsage } from "@/types";
import { formatPercent, toolUsageKey } from "@/features/metrics/utils";

/**
 * Status colours match `ToolCallStatusBadge`: emerald = completed, destructive = failed, orange = rejected.
 * The CSS variables are set on the wrapper so the dark: variants apply to the SVG and the tooltip alike.
 */
const STATUS_SERIES = [
    { dataKey: "completed_calls", name: "Completed", color: "var(--usage-completed)" },
    { dataKey: "failed_calls", name: "Failed", color: "var(--usage-failed)" },
    { dataKey: "rejected_calls", name: "Rejected", color: "var(--usage-rejected)" },
] as const;

const COLOR_VARS =
    "[--usage-completed:theme(colors.emerald.500)] dark:[--usage-completed:theme(colors.emerald.400)] " +
    "[--usage-failed:hsl(var(--destructive))] dark:[--usage-failed:theme(colors.red.500)] " +
    "[--usage-rejected:theme(colors.orange.500)] dark:[--usage-rejected:theme(colors.orange.400)]";

const ROW_HEIGHT = 36;
const CHART_CHROME_HEIGHT = 56;
const AXIS_TICK = { fill: "hsl(var(--muted-foreground))", fontSize: 12 };

type ChartRow = ToolUsage & { key: string };

interface ToolUsageChartProps {
    items: ToolUsage[];
}

export function ToolUsageChart({ items }: ToolUsageChartProps) {
    const rows: ChartRow[] = items.map((item) => ({ ...item, key: toolUsageKey(item) }));
    const toolNameByKey = new Map(rows.map((row) => [row.key, row.tool_name]));
    const height = rows.length * ROW_HEIGHT + CHART_CHROME_HEIGHT;

    return (
        <div className={COLOR_VARS} data-testid="tool-usage-chart">
            <ResponsiveContainer width="100%" height={height}>
                <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }} barCategoryGap="25%">
                    <CartesianGrid horizontal={false} stroke="hsl(var(--border))" strokeDasharray="3 3" />
                    <XAxis type="number" allowDecimals={false} tick={AXIS_TICK} axisLine={false} tickLine={false} />
                    <YAxis
                        type="category"
                        dataKey="key"
                        width={160}
                        tick={AXIS_TICK}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(key: string) => truncate(toolNameByKey.get(key) ?? key, 22)}
                    />
                    <Tooltip
                        cursor={{ fill: "hsl(var(--muted))", opacity: 0.5 }}
                        content={({ active, payload }) => (
                            <UsageTooltip active={active} row={payload?.[0]?.payload as ChartRow | undefined} />
                        )}
                    />
                    <Legend
                        iconType="circle"
                        iconSize={8}
                        wrapperStyle={{ fontSize: 12 }}
                        formatter={(value) => <span className="text-muted-foreground">{value}</span>}
                    />
                    {STATUS_SERIES.map((series) => (
                        <Bar key={series.dataKey} dataKey={series.dataKey} name={series.name} stackId="calls" fill={series.color} />
                    ))}
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}

function UsageTooltip({ active, row }: { active?: boolean; row?: ChartRow }) {
    if (!active || !row) return null;

    return (
        <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
            <div className="font-mono font-semibold">{row.tool_name}</div>
            <div className="mb-2 text-muted-foreground">{row.server_name}</div>
            <div className="space-y-1">
                {STATUS_SERIES.map((series) => (
                    <div key={series.dataKey} className="flex items-center justify-between gap-6">
                        <span className="flex items-center gap-1.5">
                            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: series.color }} />
                            {series.name}
                        </span>
                        <span className="font-mono">{row[series.dataKey]}</span>
                    </div>
                ))}
                <div className="flex items-center justify-between gap-6 border-t border-border pt-1 font-medium">
                    <span>Total</span>
                    <span className="font-mono">{row.total_calls}</span>
                </div>
                <div className="flex items-center justify-between gap-6 text-muted-foreground">
                    <span>Success rate</span>
                    <span className="font-mono">{formatPercent(row.completed_calls, row.total_calls)}</span>
                </div>
            </div>
        </div>
    );
}

function truncate(value: string, max: number): string {
    return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}
