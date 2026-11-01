import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import React, { Suspense } from "react";
import ToolDetailPage from "@/app/(dashboard)/tools/[toolId]/page";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mockTool = {
    id: "srv-1:calculate",
    name: "calculate",
    description: "Evaluates mathematical expression safely",
    server_id: "srv-1",
    server_name: "math-server",
    availability_status: "AVAILABLE",
    last_discovered_at: "2026-10-24T15:00:00Z",
    input_schema: {
        type: "object",
        properties: {
            expression: {
                type: "string",
                description: "Math formula to evaluate",
            },
            precision: {
                type: "integer",
                description: "Rounding decimals",
                default: 2,
                minimum: 0,
                maximum: 8,
            },
            mode: {
                type: "string",
                enum: ["fast", "precise"],
            },
        },
        required: ["expression"],
    },
};

vi.mock("@/features/tools/hooks/use-tools", () => ({
    useTool: (id: string) => {
        if (id === "not-found") {
            return {
                data: null,
                isLoading: false,
                isError: true,
                error: new Error("Tool with id 'not-found' not found"),
                refetch: vi.fn(),
            };
        }
        return {
            data: mockTool,
            isLoading: false,
            isError: false,
            error: null,
            refetch: vi.fn(),
        };
    },
}));

function renderWithClient(ui: React.ReactElement) {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    return render(
        <QueryClientProvider client={queryClient}>
            <Suspense fallback={<div>Loading page...</div>}>{ui}</Suspense>
        </QueryClientProvider>
    );
}

async function renderDetailPage(toolId: string) {
    const paramsPromise = Promise.resolve({ toolId });
    await act(async () => {
        renderWithClient(<ToolDetailPage params={paramsPromise} />);
    });
}

describe("ToolDetailPage Component", () => {
    beforeEach(() => {
        Object.assign(navigator, {
            clipboard: {
                writeText: vi.fn().mockResolvedValue(undefined),
            },
        });
    });

    it("renders tool header, server link, and status badge", async () => {
        await renderDetailPage("srv-1%3Acalculate");

        await waitFor(() => {
            expect(screen.getByText("calculate")).toBeInTheDocument();
            expect(
                screen.getByText("Evaluates mathematical expression safely")
            ).toBeInTheDocument();
            expect(screen.getByText("math-server")).toBeInTheDocument();
            expect(screen.getByText("Available")).toBeInTheDocument();
        });
    });

    it("renders parameter breakdown table with required and optional tags", async () => {
        await renderDetailPage("srv-1:calculate");

        await waitFor(() => {
            expect(screen.getByText("expression")).toBeInTheDocument();
            expect(screen.getByText("precision")).toBeInTheDocument();
            expect(screen.getByText("mode")).toBeInTheDocument();

            expect(screen.getAllByText("Required").length).toBeGreaterThanOrEqual(1);
            expect(screen.getAllByText("Optional").length).toBe(2);
            expect(screen.getByText("Rounding decimals")).toBeInTheDocument();
        });
    });

    it("switches to Invocation API tab and displays cURL and Python gateway snippets", async () => {
        await renderDetailPage("srv-1:calculate");

        const codeTab = screen.getByRole("tab", { name: /Invocation API/i });
        fireEvent.click(codeTab);

        await waitFor(() => {
            expect(screen.getByText(/REST API Execution \(cURL\)/i)).toBeInTheDocument();
            expect(
                screen.getByText(/Unified MCP Gateway \(\/mcp\) Python Client/i)
            ).toBeInTheDocument();
        });

        const copyBtns = screen.getAllByRole("button", { name: /Copy cURL/i });
        fireEvent.click(copyBtns[0]);
        expect(navigator.clipboard.writeText).toHaveBeenCalled();
    });

    it("renders error state when tool is not found", async () => {
        await renderDetailPage("not-found");

        await waitFor(() => {
            expect(screen.getByText("Tool Not Found")).toBeInTheDocument();
        });
    });
});
