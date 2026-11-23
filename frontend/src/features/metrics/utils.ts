import { ToolUsage } from "@/types";

/** Stable identity of a tool: the same tool name can exist on several Servers. */
export function toolUsageKey(item: Pick<ToolUsage, "server_id" | "tool_name">): string {
    return `${item.server_id}:${item.tool_name}`;
}

/** `part / whole` as a percentage with one decimal, or "-" when `whole` is 0. */
export function formatPercent(part: number, whole: number): string {
    if (whole <= 0) return "-";
    return `${((part / whole) * 100).toFixed(1)}%`;
}
