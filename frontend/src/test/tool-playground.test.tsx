import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { ToolPlayground } from "@/features/playground/components/ToolPlayground";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mockMutateAsync = vi.fn();
let mockSearchParams = new URLSearchParams("server=srv-1&tool=calculate");

vi.mock("next/navigation", () => ({
    useSearchParams: () => mockSearchParams,
    useRouter: () => ({
        replace: vi.fn(),
        push: vi.fn(),
    }),
}));

vi.mock("@/features/servers/hooks/use-servers", () => ({
    useServers: () => ({
        data: {
            items: [{ id: "srv-1", name: "Math Server", transport: "stdio" }],
        },
    }),
}));

vi.mock("@/features/tools/hooks/use-tools", () => ({
    useTools: () => ({
        data: {
            items: [
                {
                    id: "srv-1:calculate",
                    name: "calculate",
                    description: "Evaluate math expression",
                    server_id: "srv-1",
                    server_name: "Math Server",
                    availability_status: "AVAILABLE",
                    last_discovered_at: "2026-10-24T15:00:00Z",
                    input_schema: {
                        type: "object",
                        properties: {
                            expression: { type: "string" },
                        },
                        required: ["expression"],
                    },
                },
                {
                    id: "srv-1:delete_record",
                    name: "delete_record",
                    description: "Delete database record",
                    server_id: "srv-1",
                    server_name: "Math Server",
                    availability_status: "AVAILABLE",
                    last_discovered_at: "2026-10-24T15:00:00Z",
                    input_schema: {
                        type: "object",
                        properties: {
                            id: { type: "string" },
                        },
                        required: ["id"],
                    },
                },
            ],
        },
        isLoading: false,
    }),
    useExecuteTool: () => ({
        mutateAsync: mockMutateAsync,
        isPending: false,
    }),
}));

function renderWithClient(ui: React.ReactElement) {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("ToolPlayground Component", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockSearchParams = new URLSearchParams("server=srv-1&tool=calculate");
        Object.assign(navigator, {
            clipboard: {
                writeText: vi.fn().mockResolvedValue(undefined),
            },
        });
    });

    it("renders active tool and schema input fields", () => {
        renderWithClient(<ToolPlayground />);

        expect(screen.getByText("Evaluate math expression")).toBeInTheDocument();
        expect(screen.getByText("expression")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /Execute Tool/i })).toBeInTheDocument();
    });

    it("switches to JSON mode and accepts custom JSON payload", () => {
        renderWithClient(<ToolPlayground />);

        const jsonTab = screen.getByRole("tab", { name: /JSON/i });
        fireEvent.click(jsonTab);

        const textarea = screen.getByPlaceholderText("{}");
        expect(textarea).toBeInTheDocument();

        fireEvent.change(textarea, { target: { value: '{"expression": "4 * 5"}' } });
        expect(textarea).toHaveValue('{"expression": "4 * 5"}');
    });

    it("executes tool invocation and displays result content", async () => {
        mockMutateAsync.mockResolvedValueOnce({
            execution_id: "exec-12345678",
            server_id: "srv-1",
            tool_name: "calculate",
            is_error: false,
            content: [{ type: "text", text: "20" }],
            structured_content: { result: 20 },
            duration_ms: 12.5,
            executed_at: "2026-10-24T15:00:00Z",
        });

        renderWithClient(<ToolPlayground />);

        const input = screen.getByRole("textbox");
        fireEvent.change(input, { target: { value: "4 * 5" } });

        const executeBtn = screen.getByRole("button", { name: /Execute Tool/i });
        fireEvent.click(executeBtn);

        await waitFor(() => {
            expect(mockMutateAsync).toHaveBeenCalledWith({
                serverId: "srv-1",
                toolName: "calculate",
                payload: { arguments: { expression: "4 * 5" } },
            });
            expect(screen.getByText("Success")).toBeInTheDocument();
            expect(screen.getByText("20")).toBeInTheDocument();
        });
    });

    it("prompts confirmation alert when tool name is potentially destructive", async () => {
        mockSearchParams = new URLSearchParams("server=srv-1&tool=delete_record");
        mockMutateAsync.mockResolvedValueOnce({
            execution_id: "exec-87654321",
            server_id: "srv-1",
            tool_name: "delete_record",
            is_error: false,
            content: [{ type: "text", text: "Deleted successfully" }],
            duration_ms: 5.2,
            executed_at: "2026-10-24T15:00:00Z",
        });

        renderWithClient(<ToolPlayground />);

        const input = screen.getByRole("textbox");
        fireEvent.change(input, { target: { value: "record-999" } });

        const executeBtn = screen.getByRole("button", { name: /Execute Tool/i });
        fireEvent.click(executeBtn);

        // Confirmation dialog should be visible
        await waitFor(() => {
            expect(screen.getByText(/Potentially Destructive Action/i)).toBeInTheDocument();
        });

        // Click Proceed & Execute in the dialog
        const proceedBtn = screen.getByRole("button", { name: /Proceed & Execute/i });
        fireEvent.click(proceedBtn);

        await waitFor(() => {
            expect(mockMutateAsync).toHaveBeenCalledWith({
                serverId: "srv-1",
                toolName: "delete_record",
                payload: { arguments: { id: "record-999" } },
            });
        });
    });

    it("displays error banner when execution response has is_error: true", async () => {
        mockMutateAsync.mockResolvedValueOnce({
            execution_id: "exec-err-1",
            server_id: "srv-1",
            tool_name: "calculate",
            is_error: true,
            content: [{ type: "text", text: "SyntaxError: invalid expression" }],
            duration_ms: 8.1,
            executed_at: "2026-10-24T15:00:00Z",
        });

        renderWithClient(<ToolPlayground />);

        const input = screen.getByRole("textbox");
        fireEvent.change(input, { target: { value: "invalid syntax" } });

        const executeBtn = screen.getByRole("button", { name: /Execute Tool/i });
        fireEvent.click(executeBtn);

        await waitFor(() => {
            expect(screen.getByText("Failed")).toBeInTheDocument();
            expect(screen.getByText(/Tool execution returned an error/i)).toBeInTheDocument();
            expect(screen.getByText("SyntaxError: invalid expression")).toBeInTheDocument();
        });
    });
});
