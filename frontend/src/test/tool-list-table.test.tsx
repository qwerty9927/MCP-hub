import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { ToolListTable } from "@/features/tools/components/ToolListTable";
import { ToolRead } from "@/types";

const mockTools: ToolRead[] = [
    {
        id: "server-uuid-1:calculate",
        name: "calculate",
        description: "Perform math calculation",
        input_schema: {
            type: "object",
            properties: {
                expression: { type: "string" },
                precision: { type: "integer" },
            },
            required: ["expression"],
        },
        server_id: "server-uuid-1",
        server_name: "math-server",
        availability_status: "AVAILABLE",
        last_discovered_at: "2026-10-24T15:00:00Z",
    },
    {
        id: "server-uuid-2:delete_data",
        name: "delete_data",
        description: "Purge records",
        input_schema: {
            type: "object",
            properties: {},
        },
        server_id: "server-uuid-2",
        server_name: "db-server",
        availability_status: "UNAVAILABLE",
        last_discovered_at: "2026-10-24T15:30:00Z",
    },
];

describe("ToolListTable Component", () => {
    beforeEach(() => {
        Object.assign(navigator, {
            clipboard: {
                writeText: vi.fn().mockResolvedValue(undefined),
            },
        });
    });

    it("renders tool details, server name, and parameters count", () => {
        render(<ToolListTable tools={mockTools} />);

        expect(screen.getByText("calculate")).toBeInTheDocument();
        expect(screen.getByText("delete_data")).toBeInTheDocument();
        expect(screen.getByText("math-server")).toBeInTheDocument();
        expect(screen.getByText("db-server")).toBeInTheDocument();

        expect(screen.getByText("2 params (1 req)")).toBeInTheDocument();
        expect(screen.getByText("0 params")).toBeInTheDocument();

        expect(screen.getByText("Available")).toBeInTheDocument();
        expect(screen.getByText("Unavailable")).toBeInTheDocument();
    });

    it("provides link to playground with server and tool params", () => {
        render(<ToolListTable tools={mockTools} />);

        const links = screen.getAllByRole("link", { name: /Test/i });
        expect(links[0]).toHaveAttribute("href", "/playground?server=server-uuid-1&tool=calculate");
    });

    it("opens quick preview dialog when eye button is clicked", async () => {
        render(<ToolListTable tools={mockTools} />);

        const previewBtns = screen.getAllByTitle("Quick Schema Preview");
        fireEvent.click(previewBtns[0]);

        await waitFor(() => {
            expect(screen.getByRole("dialog")).toBeInTheDocument();
            expect(screen.getByText("Parameters (2)")).toBeInTheDocument();
            expect(screen.getAllByText("Perform math calculation").length).toBeGreaterThanOrEqual(
                2
            );
        });
    });

    it("copies qualified tool ID to clipboard when copy button clicked", async () => {
        render(<ToolListTable tools={mockTools} />);

        const copyBtns = screen.getAllByTitle("Copy qualified ID");
        fireEvent.click(copyBtns[0]);

        expect(navigator.clipboard.writeText).toHaveBeenCalledWith("server-uuid-1:calculate");
    });
});
