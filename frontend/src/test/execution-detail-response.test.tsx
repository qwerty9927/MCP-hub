import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import React, { Suspense } from "react";
import ExecutionDetailPage from "@/app/(dashboard)/executions/[executionId]/page";
import { ExecutionRecord } from "@/types";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

let mockExecutionData: ExecutionRecord | null = null;
let mockIsLoading = false;
let mockIsError = false;

vi.mock("@/features/executions/hooks/use-executions", () => ({
    useExecution: () => ({
        data: mockExecutionData,
        isLoading: mockIsLoading,
        isError: mockIsError,
        error: mockIsError ? new Error("Execution not found") : null,
        refetch: vi.fn(),
    }),
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

async function renderDetailPage(executionId: string) {
    const paramsPromise = Promise.resolve({ executionId });
    await act(async () => {
        renderWithClient(<ExecutionDetailPage params={paramsPromise} />);
    });
}

describe("ExecutionDetailPage Component with Response Payload", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockIsLoading = false;
        mockIsError = false;

        Object.assign(navigator, {
            clipboard: {
                writeText: vi.fn().mockImplementation(() => Promise.resolve()),
            },
        });
    });

    it("renders execution details with response content blocks and structured content", async () => {
        mockExecutionData = {
            id: "exec-101",
            server_id: "srv-alpha",
            server_name: "math-server",
            tool_name: "calculate_expression",
            arguments: { expr: "2 * (10 + 5)" },
            is_error: false,
            duration_ms: 18.5,
            executed_at: "2026-11-07T10:00:00Z",
            response: {
                content: [
                    {
                        type: "text",
                        text: "Result: 30",
                    },
                ],
                structured_content: {
                    result: 30,
                    operation_count: 2,
                },
            },
        };

        await renderDetailPage("exec-101");

        await waitFor(() => {
            // Header and metrics
            expect(screen.getByText("Execution: calculate_expression")).toBeInTheDocument();
            expect(screen.getByText("Completed")).toBeInTheDocument();
            expect(screen.getByText("18.5ms")).toBeInTheDocument();
            expect(screen.getByText("math-server")).toBeInTheDocument();

            // Invocation Arguments
            expect(screen.getByText(/"expr": "2 \* \(10 \+ 5\)"/)).toBeInTheDocument();

            // Response Output Card
            expect(screen.getByText("Tool Output Response")).toBeInTheDocument();
            expect(screen.getByText("Content Blocks (1):")).toBeInTheDocument();
            expect(screen.getByText("Result: 30")).toBeInTheDocument();
            expect(screen.getByText("Structured Output:")).toBeInTheDocument();
            expect(screen.getByText(/"result": 30/)).toBeInTheDocument();
        });
    });

    it("switches to Raw JSON tab in response card", async () => {
        mockExecutionData = {
            id: "exec-102",
            server_id: "srv-alpha",
            server_name: "math-server",
            tool_name: "echo",
            arguments: { msg: "hello" },
            is_error: false,
            duration_ms: 5.2,
            executed_at: "2026-11-07T10:05:00Z",
            response: {
                content: [{ type: "text", text: "hello" }],
            },
        };

        await renderDetailPage("exec-102");

        await waitFor(() => {
            expect(screen.getByRole("tab", { name: "Raw JSON" })).toBeInTheDocument();
        });

        const rawTab = screen.getByRole("tab", { name: "Raw JSON" });
        fireEvent.click(rawTab);

        expect(screen.getByText(/"type": "text"/)).toBeInTheDocument();
    });

    it("displays error card using fallback from response.content when error_message is empty", async () => {
        mockExecutionData = {
            id: "exec-103",
            server_id: "srv-alpha",
            server_name: "math-server",
            tool_name: "divide",
            arguments: { a: 10, b: 0 },
            is_error: true,
            error_message: null,
            duration_ms: 12.0,
            executed_at: "2026-11-07T10:10:00Z",
            response: {
                content: [{ type: "text", text: "ZeroDivisionError: division by zero" }],
            },
        };

        await renderDetailPage("exec-103");

        await waitFor(() => {
            expect(screen.getByText("Failed")).toBeInTheDocument();
            expect(screen.getByText("Error Details")).toBeInTheDocument();
            expect(screen.getAllByText("ZeroDivisionError: division by zero").length).toBeGreaterThanOrEqual(1);
        });
    });

    it("copies response payload and arguments to clipboard", async () => {
        mockExecutionData = {
            id: "exec-104",
            server_id: "srv-alpha",
            server_name: "math-server",
            tool_name: "sum",
            arguments: { items: [1, 2, 3] },
            is_error: false,
            duration_ms: 14.1,
            executed_at: "2026-11-07T10:15:00Z",
            response: {
                content: [{ type: "text", text: "6" }],
            },
        };

        await renderDetailPage("exec-104");

        await waitFor(() => {
            expect(screen.getByRole("button", { name: /Copy JSON/i })).toBeInTheDocument();
        });

        // Copy JSON
        const copyJsonBtn = screen.getByRole("button", { name: /Copy JSON/i });
        fireEvent.click(copyJsonBtn);
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('"id": "exec-104"'));

        // Copy Arguments
        const copyArgsBtn = screen.getAllByRole("button", { name: "Copy" })[0];
        fireEvent.click(copyArgsBtn);
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('"items"'));
    });

    it("renders empty state when execution response is null", async () => {
        mockExecutionData = {
            id: "exec-105",
            server_id: "srv-alpha",
            server_name: "math-server",
            tool_name: "ping",
            arguments: {},
            is_error: false,
            duration_ms: 2.1,
            executed_at: "2026-11-07T10:20:00Z",
            response: null,
        };

        await renderDetailPage("exec-105");

        await waitFor(() => {
            expect(screen.getByText("No response payload recorded")).toBeInTheDocument();
            expect(screen.queryByRole("button", { name: /Copy Output/i })).not.toBeInTheDocument();
        });
    });
});
