import { describe, it, expect } from "vitest";
import { describeDelta, summarizeToolUsage } from "@/features/metrics/utils";
import { ToolUsage } from "@/types";

function usage(overrides: Partial<ToolUsage>): ToolUsage {
    return {
        server_id: "s1",
        server_name: "github-server",
        tool_name: "search_issues",
        total_calls: 0,
        completed_calls: 0,
        failed_calls: 0,
        rejected_calls: 0,
        avg_duration_ms: null,
        last_called_at: "2026-11-27T10:00:00Z",
        ...overrides,
    };
}

const ITEMS = [
    usage({ tool_name: "search_issues", total_calls: 30, completed_calls: 27, failed_calls: 2, rejected_calls: 1, avg_duration_ms: 100 }),
    usage({ tool_name: "create_issue", total_calls: 10, completed_calls: 10, avg_duration_ms: 300 }),
    usage({ server_id: "s2", server_name: "postgres-mcp", tool_name: "query", total_calls: 5, failed_calls: 5, avg_duration_ms: null }),
];

describe("summarizeToolUsage", () => {
    it("totals every row and weights the average duration by calls", () => {
        const summary = summarizeToolUsage(ITEMS);

        expect(summary.totalCalls).toBe(45);
        expect(summary.completedCalls).toBe(37);
        expect(summary.failedCalls).toBe(7);
        expect(summary.rejectedCalls).toBe(1);
        // (100 × 30 + 300 × 10) / 40; the row without a duration is left out of the average.
        expect(summary.avgDurationMs).toBe(150);
    });

    it("keeps only one server's rows when a server id is given", () => {
        const summary = summarizeToolUsage(ITEMS, "s2");

        expect(summary.items.map((item) => item.tool_name)).toEqual(["query"]);
        expect(summary.totalCalls).toBe(5);
        expect(summary.failedCalls).toBe(5);
        expect(summary.avgDurationMs).toBeNull();
    });

    it("describes the change from the previous period", () => {
        expect(describeDelta(1284, 1000)).toEqual({ direction: "up", label: "28.4%" });
        expect(describeDelta(50, 100)).toEqual({ direction: "down", label: "50.0%" });
        expect(describeDelta(7, 7)).toEqual({ direction: "flat", label: "0%" });
        expect(describeDelta(5, 0)).toEqual({ direction: "new", label: "New" });
        expect(describeDelta(0, 0)).toEqual({ direction: "flat", label: "0%" });
        // All time has no previous period.
        expect(describeDelta(5, null)).toBeNull();
        expect(describeDelta(5, undefined)).toBeNull();
    });

    it("returns zeros and no average for no rows", () => {
        expect(summarizeToolUsage([])).toEqual({
            items: [],
            totalCalls: 0,
            completedCalls: 0,
            failedCalls: 0,
            rejectedCalls: 0,
            avgDurationMs: null,
        });
    });
});
