import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import React from "react";
import MetricsPage from "@/app/(dashboard)/metrics/page";
import { ToolUsageReport } from "@/types";

const { mockUseToolUsage } = vi.hoisted(() => ({ mockUseToolUsage: vi.fn() }));

vi.mock("@/features/metrics/hooks/use-tool-usage", () => ({
    useToolUsage: mockUseToolUsage,
}));

// jsdom has no layout, so ResponsiveContainer would measure 0x0 and render nothing.
vi.mock("recharts", async (importOriginal) => {
    const actual = await importOriginal<typeof import("recharts")>();
    return {
        ...actual,
        ResponsiveContainer: ({ children }: { children: React.ReactElement<{ width?: number; height?: number }> }) => (
            <div style={{ width: 800, height: 400 }}>{React.cloneElement(children, { width: 800, height: 400 })}</div>
        ),
    };
});

const report: ToolUsageReport = {
    range: "7d",
    since: "2026-11-16T00:00:00Z",
    total_calls: 200,
    items: [
        {
            server_id: "srv-1",
            server_name: "search-server",
            tool_name: "web_search",
            total_calls: 60,
            completed_calls: 54,
            failed_calls: 4,
            rejected_calls: 2,
            avg_duration_ms: 420.5,
            last_called_at: "2026-11-23T08:00:00Z",
        },
        {
            server_id: "srv-2",
            server_name: "files-server",
            tool_name: "read_file",
            total_calls: 30,
            completed_calls: 30,
            failed_calls: 0,
            rejected_calls: 0,
            avg_duration_ms: 12,
            last_called_at: "2026-11-22T08:00:00Z",
        },
        {
            server_id: "srv-2",
            server_name: "files-server",
            tool_name: "write_file",
            total_calls: 10,
            completed_calls: 5,
            failed_calls: 3,
            rejected_calls: 2,
            avg_duration_ms: null,
            last_called_at: "2026-11-21T08:00:00Z",
        },
    ],
};

function queryResult(overrides: Record<string, unknown>) {
    return { data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn(), ...overrides };
}

describe("Metrics page", () => {
    beforeEach(() => {
        mockUseToolUsage.mockReset();
    });

    it("requests the last 7 days of the top 10 tools by default", () => {
        mockUseToolUsage.mockReturnValue(queryResult({ data: report }));
        render(<MetricsPage />);

        expect(mockUseToolUsage).toHaveBeenCalledWith("7d", 10);
        expect(screen.getByRole("tab", { name: "7d" })).toHaveAttribute("data-state", "active");
    });

    it("ranks tools by calls with their share of all calls and success rate", () => {
        mockUseToolUsage.mockReturnValue(queryResult({ data: report }));
        render(<MetricsPage />);

        const rows = screen.getAllByTestId("tool-usage-row");
        expect(rows).toHaveLength(3);

        const [first, second, third] = rows.map((row) => within(row));
        expect(first.getByText("1")).toBeInTheDocument();
        expect(first.getByText("web_search")).toBeInTheDocument();
        expect(first.getByText("search-server")).toBeInTheDocument();
        expect(first.getByText("30.0%")).toBeInTheDocument(); // 60 of 200 calls
        expect(first.getByText("90.0%")).toBeInTheDocument(); // 54 of 60 completed

        expect(second.getByText("read_file")).toBeInTheDocument();
        expect(second.getByText("15.0%")).toBeInTheDocument();
        expect(second.getByText("100.0%")).toBeInTheDocument();

        expect(third.getByText("write_file")).toBeInTheDocument();
        expect(third.getByText("5.0%")).toBeInTheDocument();
        expect(third.getByText("50.0%")).toBeInTheDocument();
        expect(third.getByText("-")).toBeInTheDocument(); // no average duration
    });

    it("summarises the range and draws the chart", () => {
        mockUseToolUsage.mockReturnValue(queryResult({ data: report }));
        const { container } = render(<MetricsPage />);

        expect(screen.getByText("Calls in range")).toBeInTheDocument();
        expect(screen.getByText("200")).toBeInTheDocument();
        expect(screen.getByText("Distinct tools")).toBeInTheDocument();
        expect(screen.getByText("Most-used tool")).toBeInTheDocument();
        expect(screen.getByTitle("web_search")).toBeInTheDocument();
        expect(screen.getByText(/These tools account for 50\.0% of all calls/)).toBeInTheDocument();

        expect(screen.getByTestId("tool-usage-chart")).toBeInTheDocument();
        expect(container.querySelector(".recharts-bar")).not.toBeNull();
    });

    it("requests the new range when switching to 24h", () => {
        mockUseToolUsage.mockReturnValue(queryResult({ data: report }));
        render(<MetricsPage />);

        fireEvent.click(screen.getByRole("tab", { name: "24h" }));

        expect(mockUseToolUsage).toHaveBeenLastCalledWith("24h", 10);
        expect(screen.getByRole("tab", { name: "24h" })).toHaveAttribute("data-state", "active");
    });

    it("shows an empty state linking to the playground when there are no calls", () => {
        mockUseToolUsage.mockReturnValue(queryResult({ data: { range: "7d", since: null, total_calls: 0, items: [] } }));
        render(<MetricsPage />);

        expect(screen.getByText("No tool calls yet")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Run a Tool in Playground" })).toHaveAttribute("href", "/playground");
        expect(screen.queryByTestId("tool-usage-row")).not.toBeInTheDocument();
    });

    it("shows the error with a retry", () => {
        const refetch = vi.fn();
        mockUseToolUsage.mockReturnValue(queryResult({ isError: true, error: new Error("Network down"), refetch }));
        render(<MetricsPage />);

        expect(screen.getByText("Failed to load tool usage")).toBeInTheDocument();
        expect(screen.getByText("Network down")).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: /Retry/i }));
        expect(refetch).toHaveBeenCalled();
    });

    it("shows skeletons while loading", () => {
        mockUseToolUsage.mockReturnValue(queryResult({ isLoading: true }));
        render(<MetricsPage />);

        expect(screen.queryByTestId("tool-usage-row")).not.toBeInTheDocument();
        expect(screen.queryByText("No tool calls yet")).not.toBeInTheDocument();
        expect(screen.getByRole("table")).toBeInTheDocument();
    });
});
