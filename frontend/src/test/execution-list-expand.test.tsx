import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { ExecutionListTable } from "@/features/executions/components/ExecutionListTable";
import { ExecutionFilterBar } from "@/features/executions/components/ExecutionFilterBar";
import { ExecutionRecord } from "@/types";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/features/servers/hooks/use-servers", () => ({
    useServers: () => ({
        data: {
            items: [
                { id: "srv-1", name: "Server One" },
                { id: "srv-2", name: "Server Two" },
            ],
        },
    }),
}));

const mockExecutions: ExecutionRecord[] = [
    {
        id: "exec-001",
        server_id: "srv-1",
        server_name: "Server One",
        tool_name: "multiply",
        arguments: { a: 5, b: 6 },
        is_error: false,
        duration_ms: 15.3,
        executed_at: "2026-11-07T09:00:00Z",
        response: {
            content: [{ type: "text", text: "Product is 30" }],
            structured_content: { result: 30 },
        },
    },
    {
        id: "exec-002",
        server_id: "srv-2",
        server_name: "Server Two",
        tool_name: "fetch_url",
        arguments: { url: "https://bad.host" },
        is_error: true,
        error_message: "DNS lookup failure: NXDOMAIN",
        duration_ms: 120.4,
        executed_at: "2026-11-07T09:05:00Z",
        response: null,
    },
];

function renderWithClient(ui: React.ReactElement) {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("ExecutionListTable Component", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("renders executions table with status, tool, server, duration, and details action", () => {
        renderWithClient(<ExecutionListTable executions={mockExecutions} />);

        // Table headers and rows
        expect(screen.getByText("multiply")).toBeInTheDocument();
        expect(screen.getByText("fetch_url")).toBeInTheDocument();
        expect(screen.getByText("Server One")).toBeInTheDocument();
        expect(screen.getByText("Server Two")).toBeInTheDocument();
        expect(screen.getByText("Success")).toBeInTheDocument();
        expect(screen.getByText("Failed")).toBeInTheDocument();

        // Details links
        const detailsLinks = screen.getAllByRole("link", { name: "Details" });
        expect(detailsLinks.length).toBe(2);
        expect(detailsLinks[0]).toHaveAttribute("href", "/executions/exec-001");
        expect(detailsLinks[1]).toHaveAttribute("href", "/executions/exec-002");
    });
});

describe("ExecutionFilterBar Refresh & Live Controls", () => {
    it("renders filter controls and triggers refresh on button click", () => {
        const mockRefresh = vi.fn();
        const mockToggleAutoRefresh = vi.fn();

        renderWithClient(
            <ExecutionFilterBar
                filters={{ page: 1, page_size: 20 }}
                onChange={vi.fn()}
                onRefresh={mockRefresh}
                isRefreshing={false}
                autoRefresh={false}
                onToggleAutoRefresh={mockToggleAutoRefresh}
            />
        );

        // Check search and filter elements
        expect(screen.getByPlaceholderText("Filter by tool name...")).toBeInTheDocument();
        expect(screen.getByText("Live (10s)")).toBeInTheDocument();

        // Click refresh button
        const refreshBtn = screen.getByRole("button", { name: /Refresh/i });
        fireEvent.click(refreshBtn);
        expect(mockRefresh).toHaveBeenCalledTimes(1);

        // Toggle auto refresh
        const switchElement = screen.getByRole("switch", { name: /Toggle auto refresh/i });
        fireEvent.click(switchElement);
        expect(mockToggleAutoRefresh).toHaveBeenCalledWith(true);
    });
});
