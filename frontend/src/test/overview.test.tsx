import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => "/overview" }));

const api = vi.hoisted(() => ({
    metrics: vi.fn(async () => ({
        active_sessions: 2,
        total_servers: 3,
        healthy_servers: 2,
        total_executions: 90,
        uptime_seconds: 10,
    })),
    servers: vi.fn(async () => ({
        items: [
            { id: "s1", name: "github-server", transport: "stdio", discovered_tool_count: 15, health_status: "HEALTHY" },
            { id: "s2", name: "postgres-mcp", transport: "streamable-http", discovered_tool_count: 8, health_status: "HEALTHY" },
            { id: "s3", name: "slack-bridge", transport: "streamable-http", discovered_tool_count: 0, health_status: "UNHEALTHY" },
        ],
        total: 3,
    })),
    tools: vi.fn(async () => ({ items: [], total: 23 })),
}));

vi.mock("@/lib/api", () => ({
    systemApi: { metrics: api.metrics },
    serversApi: { list: api.servers },
    toolsApi: { list: api.tools },
}));

vi.mock("@/features/metrics/hooks/use-tool-usage", () => ({
    useToolUsage: () => ({
        data: {
            range: "24h",
            since: null,
            total_calls: 1284,
            previous_total_calls: 1000,
            p90_duration_ms: 240,
            items: [
                {
                    server_id: "s1",
                    server_name: "github-server",
                    tool_name: "search_issues",
                    total_calls: 1200,
                    completed_calls: 1190,
                    failed_calls: 7,
                    rejected_calls: 3,
                    avg_duration_ms: 120,
                    last_called_at: "2026-11-27T10:00:00Z",
                },
                {
                    server_id: "s2",
                    server_name: "postgres-mcp",
                    tool_name: "query",
                    total_calls: 84,
                    completed_calls: 84,
                    failed_calls: 0,
                    rejected_calls: 0,
                    avg_duration_ms: 120,
                    last_called_at: "2026-11-27T10:00:00Z",
                },
            ],
        },
        isLoading: false,
        isFetching: false,
        refetch: vi.fn(),
    }),
}));

const trend = vi.hoisted(() => ({
    data: {
        range: "24h",
        since: "2026-11-26T10:00:00Z",
        bucket_seconds: 3600,
        buckets: [
            { start: "2026-11-27T08:00:00Z", total_calls: 0, completed_calls: 0, failed_calls: 0, rejected_calls: 0 },
            { start: "2026-11-27T09:00:00Z", total_calls: 4, completed_calls: 3, failed_calls: 1, rejected_calls: 0 },
        ],
    } as Record<string, unknown> | undefined,
}));

vi.mock("@/features/metrics/hooks/use-calls-timeseries", () => ({
    useCallsTimeseries: () => ({ data: trend.data, isLoading: false, refetch: vi.fn() }),
}));

// The register dialog has its own tests and queries; it only mounts on use.
vi.mock("@/features/servers/components/RegisterServerDialog", () => ({ RegisterServerDialog: () => null }));

import { OverviewDashboard } from "@/features/overview/components/OverviewMetrics";
import { resetLocalStoreCache } from "@/lib/local-store";

function renderOverview() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={client}>
            <OverviewDashboard />
        </QueryClientProvider>
    );
}

function card(title: string): HTMLElement {
    return screen.getByRole("heading", { name: title }).closest(".rounded-xl") as HTMLElement;
}

beforeEach(() => {
    window.localStorage.clear();
    resetLocalStoreCache();
});

describe("Hub Overview", () => {
    it("shows servers, quick start and empty recents", async () => {
        renderOverview();

        expect(await screen.findByRole("link", { name: /github-server/ })).toHaveAttribute("href", "/servers/s1");
        expect(screen.getByText("1 unhealthy")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Register a server" })).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Browse discovery" })).toHaveAttribute("href", "/discovery");
        expect(screen.getByText("Pages you open show here.")).toBeInTheDocument();
    });

    it("calls out servers that need attention", async () => {
        renderOverview();

        expect(await screen.findByText("1 server needs attention")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Open slack-bridge" })).toHaveAttribute("href", "/servers/s3");
    });

    it("fills the analytics from tool usage and metrics", async () => {
        renderOverview();

        expect(within(card("Tool Calls")).getByText("1,284")).toBeInTheDocument();
        expect(within(card("Failed Calls")).getByText("7")).toBeInTheDocument();
        expect(within(card("Failed Calls")).getByText("search_issues")).toBeInTheDocument();
        expect(within(card("Rejected Calls")).getByText("3")).toBeInTheDocument();
        expect(within(card("P90 Latency")).getByText("240.0ms")).toBeInTheDocument();
        expect(within(card("P90 Latency")).getByText(/Avg 120\.0ms/)).toBeInTheDocument();
        expect(await within(card("Active Connections")).findByText("2")).toBeInTheDocument();
        expect(await within(card("Discovered Tools")).findByText("23")).toBeInTheDocument();
    });

    it("shows the change from the previous period and the trend chart", () => {
        trend.data = {
            range: "24h",
            since: "2026-11-26T10:00:00Z",
            bucket_seconds: 3600,
            buckets: [
                { start: "2026-11-27T08:00:00Z", total_calls: 0, completed_calls: 0, failed_calls: 0, rejected_calls: 0 },
                { start: "2026-11-27T09:00:00Z", total_calls: 4, completed_calls: 3, failed_calls: 1, rejected_calls: 0 },
            ],
        };
        renderOverview();

        // 1,284 vs 1,000 calls in the previous 24 hours.
        expect(within(card("Tool Calls")).getByLabelText("Up 28.4% from the previous period")).toBeInTheDocument();
        expect(screen.getByRole("img", { name: /Tool calls over time: 4 calls over 2 intervals/ })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Last hour" })).toBeEnabled();
    });

    it("keeps the chart's footprint with an honest empty state when there were no calls", () => {
        trend.data = { range: "24h", since: null, bucket_seconds: 3600, buckets: [] };
        renderOverview();

        expect(within(card("Tool Calls")).getByText("No calls in this range")).toBeInTheDocument();
    });

    it("marks only what the backend still can't serve as pending", () => {
        const { container } = renderOverview();

        const pending = Array.from(container.querySelectorAll("[data-pending-id]")).map((el) => el.getAttribute("data-pending-id"));
        expect(pending).toEqual(["new-tools-review"]);
    });
});
