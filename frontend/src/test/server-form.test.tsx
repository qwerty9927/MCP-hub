import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { ServerForm } from "@/features/servers/components/ServerForm";
import { ServerRead } from "@/types";

describe("ServerForm Component", () => {
    it("renders basic server fields and stdio transport by default", () => {
        render(<ServerForm onSubmit={vi.fn()} isLoading={false} />);

        expect(screen.getByLabelText(/Server Name/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/Description/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/Enabled for Execution/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/Command \/ Executable/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/Arguments/i)).toBeInTheDocument();
    });

    it("pre-fills form with initial data when in edit mode", () => {
        const mockServer: ServerRead = {
            id: "srv-123",
            name: "existing-server",
            description: "Existing math service",
            transport: "stdio",
            connection_config: {
                command: "python3",
                args: ["-m", "demo.server"],
                url: null,
                headers: null,
            },
            enabled: false,
            health_status: "HEALTHY",
            last_connected_at: null,
            last_health_check_at: null,
            discovered_tool_count: 5,
            created_at: "2026-10-24T15:00:00Z",
            updated_at: "2026-10-24T15:00:00Z",
        };

        render(<ServerForm initialData={mockServer} onSubmit={vi.fn()} isLoading={false} />);

        expect(screen.getByDisplayValue("existing-server")).toBeInTheDocument();
        expect(screen.getByDisplayValue("Existing math service")).toBeInTheDocument();
        expect(screen.getByDisplayValue("python3")).toBeInTheDocument();
        expect(screen.getByDisplayValue("-m demo.server")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /Update Server/i })).toBeInTheDocument();
    });

    it("shows validation error when required name is empty", async () => {
        const onSubmit = vi.fn();
        render(<ServerForm onSubmit={onSubmit} isLoading={false} />);

        const submitBtn = screen.getByRole("button", { name: /Register Server/i });
        fireEvent.click(submitBtn);

        await waitFor(() => {
            expect(screen.getByText(/Server name is required/i)).toBeInTheDocument();
        });
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it("submits valid stdio configuration payload", async () => {
        const onSubmit = vi.fn().mockResolvedValue(undefined);
        render(<ServerForm onSubmit={onSubmit} isLoading={false} />);

        fireEvent.change(screen.getByLabelText(/Server Name/i), {
            target: { value: "math-server" },
        });
        fireEvent.change(screen.getByLabelText(/Command \/ Executable/i), {
            target: { value: "python3" },
        });
        fireEvent.change(screen.getByLabelText(/Arguments/i), {
            target: { value: "run.py --port 8080" },
        });

        const submitBtn = screen.getByRole("button", { name: /Register Server/i });
        fireEvent.click(submitBtn);

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith({
                name: "math-server",
                description: null,
                transport: "stdio",
                enabled: true,
                stdio_config: {
                    command: "python3",
                    args: ["run.py", "--port", "8080"],
                    env: {},
                },
            });
        });
    });
});
