import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { ServerForm } from "@/features/servers/components/ServerForm";
import { ServerRead } from "@/types";
import { AppApiError } from "@/lib/errors";

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

    describe("backend refusals", () => {
        const httpServer: ServerRead = {
            id: "srv-http",
            name: "remote-tools",
            description: null,
            transport: "streamable-http",
            connection_config: { command: null, args: null, url: "https://mcp.example.com/mcp", headers: { "X-Api-Key": "********" } },
            enabled: true,
            health_status: "HEALTHY",
            last_connected_at: null,
            last_health_check_at: null,
            discovered_tool_count: 2,
            created_at: "2026-10-24T15:00:00Z",
            updated_at: "2026-10-24T15:00:00Z",
        };

        async function submitStdio(error: AppApiError, args = "") {
            const onSubmit = vi.fn().mockRejectedValue(error);
            render(<ServerForm onSubmit={onSubmit} isLoading={false} />);
            fireEvent.change(screen.getByLabelText(/Server Name/i), { target: { value: "math-server" } });
            fireEvent.change(screen.getByLabelText(/Command \/ Executable/i), { target: { value: "python3" } });
            fireEvent.change(screen.getByLabelText(/Arguments/i), { target: { value: args } });
            fireEvent.click(screen.getByRole("button", { name: /Register Server/i }));
            await waitFor(() => expect(onSubmit).toHaveBeenCalled());
        }

        it("explains that masked headers keep their saved value", () => {
            render(<ServerForm initialData={httpServer} onSubmit={vi.fn()} isLoading={false} />);

            expect(screen.getByText(/keep their saved value/i)).toBeInTheDocument();
        });

        it("marks the headers field when a masked header is not stored on the server", async () => {
            const message = "Header 'X-Token' has the masked value but is not stored on this server; send its real value";
            const onSubmit = vi.fn().mockRejectedValue(new AppApiError(message, "ValidationError", 422, { header: "X-Token" }));
            render(<ServerForm initialData={httpServer} onSubmit={onSubmit} isLoading={false} />);

            fireEvent.click(screen.getByRole("button", { name: /Update Server/i }));

            await waitFor(() => expect(screen.getByLabelText(/Request Headers/i)).toHaveAttribute("aria-invalid", "true"));
            expect(screen.getAllByText(message).length).toBeGreaterThan(0);
            expect(screen.getByLabelText(/Endpoint URL/i)).not.toHaveAttribute("aria-invalid", "true");
        });

        it("marks the name field when the name is already taken", async () => {
            await submitStdio(
                new AppApiError("A server with name 'math-server' already exists", "ConflictError", 409, { name: "math-server" })
            );

            await waitFor(() => expect(screen.getAllByText("A server with name 'math-server' already exists")).toHaveLength(2));
            expect(screen.getByLabelText(/Environment Variables/i)).not.toHaveAttribute("aria-invalid", "true");
        });

        it("marks the environment field for a refused environment variable", async () => {
            await submitStdio(
                new AppApiError("Environment variable 'LD_PRELOAD' is not allowed", "ForbiddenError", 403, { name: "LD_PRELOAD" })
            );

            await waitFor(() => expect(screen.getByLabelText(/Environment Variables/i)).toHaveAttribute("aria-invalid", "true"));
            expect(screen.getByLabelText(/Command \/ Executable/i)).not.toHaveAttribute("aria-invalid", "true");
        });

        it("marks the arguments field for a refused inline-code flag", async () => {
            await submitStdio(
                new AppApiError("Argument '-c' runs inline code", "ForbiddenError", 403, { executable: "python3", argument: "-c" }),
                "-c print(1)"
            );

            await waitFor(() => expect(screen.getByLabelText(/Arguments/i)).toHaveAttribute("aria-invalid", "true"));
        });

        it("marks the command field when stdio servers are disabled on the hub", async () => {
            const message = "Stdio servers are disabled on this hub (ALLOW_STDIO_SERVERS=false)";
            await submitStdio(new AppApiError(message, "ForbiddenError", 403));

            await waitFor(() => expect(screen.getByLabelText(/Command \/ Executable/i)).toHaveAttribute("aria-invalid", "true"));
            expect(screen.getAllByText(message).length).toBeGreaterThan(0);
        });
    });
});
