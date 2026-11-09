import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { ToolFilterBar } from "@/features/tools/components/ToolFilterBar";
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

function renderWithClient(ui: React.ReactElement) {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("ToolFilterBar Component", () => {
    it("renders search input and trigger selects", () => {
        renderWithClient(<ToolFilterBar filters={{ page: 1, page_size: 20 }} onChange={vi.fn()} />);

        expect(screen.getByPlaceholderText(/Search tools by name, description, server.../i)).toBeInTheDocument();
        expect(screen.getByText("All Servers")).toBeInTheDocument();
        expect(screen.getByText("All Statuses")).toBeInTheDocument();
    });

    it("triggers onChange when user types in search input", () => {
        const onChange = vi.fn();
        renderWithClient(<ToolFilterBar filters={{ page: 1, page_size: 20 }} onChange={onChange} />);

        const input = screen.getByPlaceholderText(/Search tools by name, description, server.../i);
        fireEvent.change(input, { target: { value: "calc" } });

        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ search: "calc", page: 1 }));
    });

    it("displays reset button when filters are active and clears filters on click", () => {
        const onChange = vi.fn();
        renderWithClient(<ToolFilterBar filters={{ page: 2, page_size: 20, search: "math" }} onChange={onChange} />);

        const resetBtn = screen.getByRole("button", { name: /Reset/i });
        expect(resetBtn).toBeInTheDocument();

        fireEvent.click(resetBtn);
        expect(onChange).toHaveBeenCalledWith({
            page: 1,
            page_size: 20,
            search: undefined,
            server_id: undefined,
            status: undefined,
        });
    });
});
