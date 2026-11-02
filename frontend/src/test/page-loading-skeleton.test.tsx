import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import ServersPage from "@/app/(dashboard)/servers/page";
import ToolsCatalogPage from "@/app/(dashboard)/tools/page";
import ExecutionsPage from "@/app/(dashboard)/executions/page";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

let mockServersLoading = true;
let mockServersError = false;
const mockRefetchServers = vi.fn();

let mockToolsLoading = true;
let mockExecutionsLoading = true;

vi.mock("@/features/servers/hooks/use-servers", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/features/servers/hooks/use-servers")>();
    return {
        ...actual,
        useServers: () => ({
            data:
                mockServersLoading || mockServersError
                    ? null
                    : {
                          items: [
                              {
                                  id: "srv-1",
                                  name: "Alpha Server",
                                  transport: "stdio",
                                  health_status: "HEALTHY",
                                  enabled: true,
                                  discovered_tool_count: 5,
                                  created_at: "2026-10-24T15:00:00Z",
                                  updated_at: "2026-10-24T15:00:00Z",
                              },
                          ],
                          total: 1,
                          total_pages: 1,
                      },
            isLoading: mockServersLoading,
            isError: mockServersError,
            error: mockServersError ? new Error("Server connection timeout") : null,
            refetch: mockRefetchServers,
        }),
    };
});

vi.mock("@/features/tools/hooks/use-tools", () => ({
    useTools: () => ({
        data: mockToolsLoading ? null : { items: [], total: 0, total_pages: 1 },
        isLoading: mockToolsLoading,
        isError: false,
        error: null,
        refetch: vi.fn(),
    }),
}));

vi.mock("@/features/executions/hooks/use-executions", () => ({
    useExecutions: () => ({
        data: mockExecutionsLoading ? null : { items: [], total: 0, total_pages: 1 },
        isLoading: mockExecutionsLoading,
        isError: false,
        error: null,
        refetch: vi.fn(),
    }),
}));

function renderWithClient(ui: React.ReactElement) {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("Page Lazy Loading with Skeleton UI", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockServersLoading = true;
        mockServersError = false;
        mockToolsLoading = true;
        mockExecutionsLoading = true;
    });

    it("displays skeleton table while servers data is loading", () => {
        renderWithClient(<ServersPage />);

        // While loading, skeleton table should be visible
        expect(screen.getByRole("table")).toBeInTheDocument();
        expect(screen.queryByText("Alpha Server")).not.toBeInTheDocument();
    });

    it("replaces skeleton with loaded servers once API call completes", () => {
        mockServersLoading = false;
        renderWithClient(<ServersPage />);

        expect(screen.getByText("Alpha Server")).toBeInTheDocument();
        expect(screen.getByText("stdio")).toBeInTheDocument();
    });

    it("renders error alert with retry button when server API request fails", () => {
        mockServersLoading = false;
        mockServersError = true;
        renderWithClient(<ServersPage />);

        expect(screen.getByText("Failed to fetch MCP servers")).toBeInTheDocument();
        expect(screen.getByText("Server connection timeout")).toBeInTheDocument();

        const retryBtn = screen.getByRole("button", { name: /Retry/i });
        fireEvent.click(retryBtn);
        expect(mockRefetchServers).toHaveBeenCalledTimes(1);
    });

    it("displays skeleton table while tools data is loading", () => {
        renderWithClient(<ToolsCatalogPage />);

        expect(screen.getByRole("table")).toBeInTheDocument();
    });

    it("displays skeleton table while executions data is loading", () => {
        renderWithClient(<ExecutionsPage />);

        expect(screen.getByRole("table")).toBeInTheDocument();
    });
});
