import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { ServerListTable } from "@/features/servers/components/ServerListTable";
import { ServerRead } from "@/types";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mockServers: ServerRead[] = [
    {
        id: "e427b3b6-733d-4c3e-862d-96116ca31614",
        name: "local-math-tools",
        description: "Safe math expression evaluation tools",
        transport: "stdio",
        connection_config: {
            command: "python3",
            args: ["-m", "demo_server.server"],
            url: null,
            headers: null,
        },
        enabled: true,
        health_status: "HEALTHY",
        last_connected_at: "2026-10-24T15:02:11Z",
        last_health_check_at: "2026-10-24T15:02:11Z",
        discovered_tool_count: 3,
        created_at: "2026-10-24T15:00:00Z",
        updated_at: "2026-10-24T15:02:11Z",
    },
    {
        id: "f827b3b6-733d-4c3e-862d-96116ca31615",
        name: "remote-http-tools",
        description: "Remote HTTP Server",
        transport: "streamable-http",
        connection_config: {
            command: null,
            args: null,
            url: "https://mcp.internal.example.com/mcp",
            headers: { Authorization: "********" },
        },
        enabled: false,
        health_status: "DISCONNECTED",
        last_connected_at: null,
        last_health_check_at: null,
        discovered_tool_count: 0,
        created_at: "2026-10-24T15:00:00Z",
        updated_at: "2026-10-24T15:00:00Z",
    },
];

describe("ServerListTable Component", () => {
    const queryClient = new QueryClient();

    it("renders server rows, transports, health badges, and tool counts", () => {
        render(
            <QueryClientProvider client={queryClient}>
                <ServerListTable servers={mockServers} />
            </QueryClientProvider>
        );

        expect(screen.getByText("local-math-tools")).toBeInTheDocument();
        expect(screen.getByText("remote-http-tools")).toBeInTheDocument();

        expect(screen.getByText("stdio")).toBeInTheDocument();
        expect(screen.getByText("HTTP")).toBeInTheDocument();

        expect(screen.getByText("Healthy")).toBeInTheDocument();
        expect(screen.getByText("Disconnected")).toBeInTheDocument();

        expect(screen.getByText("3")).toBeInTheDocument();
        expect(screen.getByText("0")).toBeInTheDocument();
    });

    const openRowMenu = async (server: ServerRead) => {
        render(
            <QueryClientProvider client={queryClient}>
                <ServerListTable servers={[server]} />
            </QueryClientProvider>
        );
        await userEvent.setup().click(screen.getByRole("button", { name: "Open menu" }));
        await screen.findByRole("menuitem", { name: "Refresh Tools" });
    };

    // Refresh Tools connects and re-syncs; the Enabled switch is the on/off control.
    it.each([
        ["healthy server", mockServers[0]],
        ["disconnected server", mockServers[1]],
        [
            "disconnected OAuth server",
            { ...mockServers[1], auth_type: "oauth", oauth_provider_id: "atlassian", enabled: true } as ServerRead,
        ],
    ])("row menu of a %s has no Connect or Disconnect", async (_label, server) => {
        await openRowMenu(server);

        expect(screen.queryByRole("menuitem", { name: /^(connect|disconnect)/i })).not.toBeInTheDocument();
        expect(screen.getByRole("menuitem", { name: "Test Connection" })).toBeInTheDocument();
    });
});
