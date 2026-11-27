import { ToolUsage } from "@/types";

/** Stable identity of a tool: the same tool name can exist on several Servers. */
export function toolUsageKey(item: Pick<ToolUsage, "server_id" | "tool_name">): string {
    return `${item.server_id}:${item.tool_name}`;
}

export interface ToolUsageSummary {
    /** The usage rows counted (all, or one Server's), still sorted by calls. */
    items: ToolUsage[];
    totalCalls: number;
    completedCalls: number;
    failedCalls: number;
    rejectedCalls: number;
    /** Mean duration weighted by each tool's calls; null when no row has a duration. */
    avgDurationMs: number | null;
}

/**
 * Totals over tool-usage rows, optionally for one Server. The report lists at most `limit` tools, so the totals
 * cover those rows; the report's own `total_calls` is the exact count across every tool.
 */
export function summarizeToolUsage(items: ToolUsage[], serverId?: string): ToolUsageSummary {
    const rows = serverId ? items.filter((item) => item.server_id === serverId) : items;
    let weighted = 0;
    let timedCalls = 0;
    const summary = rows.reduce(
        (acc, item) => {
            acc.totalCalls += item.total_calls;
            acc.completedCalls += item.completed_calls;
            acc.failedCalls += item.failed_calls;
            acc.rejectedCalls += item.rejected_calls;
            if (item.avg_duration_ms !== null && item.avg_duration_ms !== undefined) {
                weighted += item.avg_duration_ms * item.total_calls;
                timedCalls += item.total_calls;
            }
            return acc;
        },
        { totalCalls: 0, completedCalls: 0, failedCalls: 0, rejectedCalls: 0 }
    );
    return { items: rows, ...summary, avgDurationMs: timedCalls > 0 ? weighted / timedCalls : null };
}

export interface Delta {
    direction: "up" | "down" | "flat" | "new";
    /** e.g. "12.4%", or "New" when the previous period had no calls. */
    label: string;
}

/** Change from the previous period; null when there is nothing to compare with (all time). */
export function describeDelta(current: number, previous: number | null | undefined): Delta | null {
    if (previous === null || previous === undefined) return null;
    if (previous === 0) return current === 0 ? { direction: "flat", label: "0%" } : { direction: "new", label: "New" };
    const change = ((current - previous) / previous) * 100;
    if (Math.abs(change) < 0.05) return { direction: "flat", label: "0%" };
    return { direction: change > 0 ? "up" : "down", label: `${Math.abs(change).toFixed(1)}%` };
}

/** `part / whole` as a percentage with one decimal, or "-" when `whole` is 0. */
export function formatPercent(part: number, whole: number): string {
    if (whole <= 0) return "-";
    return `${((part / whole) * 100).toFixed(1)}%`;
}
