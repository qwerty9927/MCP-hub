import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
    useConnectServer,
    useDisconnectServer,
    useTestServerConnection,
    useDeleteServer,
    useRefreshServerTools,
} from "@/features/servers/hooks/use-servers";
import { serversApi } from "@/lib/api";
import { ServerRead } from "@/types";

vi.mock("@/lib/api", () => ({
    serversApi: {
        connect: vi.fn(),
        disconnect: vi.fn(),
        testConnection: vi.fn(),
        delete: vi.fn(),
        update: vi.fn(),
        refreshTools: vi.fn(),
    },
}));

vi.mock("sonner", () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
        info: vi.fn(),
    },
}));

const mockServer: ServerRead = {
    id: "test-server-uuid",
    name: "test-server",
    description: "Test description",
    transport: "stdio",
    connection_config: {
        command: "python3",
        args: ["-m", "server"],
        url: null,
        headers: null,
    },
    enabled: true,
    health_status: "HEALTHY",
    last_connected_at: "2026-10-24T15:00:00Z",
    last_health_check_at: "2026-10-24T15:00:00Z",
    discovered_tool_count: 2,
    created_at: "2026-10-24T15:00:00Z",
    updated_at: "2026-10-24T15:00:00Z",
};

describe("Server Management Actions Hooks", () => {
    let queryClient: QueryClient;

    beforeEach(() => {
        queryClient = new QueryClient({
            defaultOptions: {
                queries: { retry: false },
                mutations: { retry: false },
            },
        });
        vi.clearAllMocks();
    });

    const wrapper = ({ children }: { children: React.ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    it("executes connectServer mutation successfully", async () => {
        (serversApi.connect as any).mockResolvedValue({
            ...mockServer,
            health_status: "HEALTHY",
            discovered_tool_count: 3,
        });

        const { result } = renderHook(() => useConnectServer(), { wrapper });

        await result.current.mutateAsync("test-server-uuid");

        expect(serversApi.connect).toHaveBeenCalledWith("test-server-uuid");
    });

    it("executes disconnectServer mutation successfully", async () => {
        (serversApi.disconnect as any).mockResolvedValue({
            ...mockServer,
            health_status: "DISCONNECTED",
        });

        const { result } = renderHook(() => useDisconnectServer(), { wrapper });

        await result.current.mutateAsync("test-server-uuid");

        expect(serversApi.disconnect).toHaveBeenCalledWith("test-server-uuid");
    });

    it("executes testConnection mutation and returns test probe result", async () => {
        (serversApi.testConnection as any).mockResolvedValue({
            success: true,
            message: "Connection verified",
            tools_count: 2,
            latency_ms: 24.5,
        });

        const { result } = renderHook(() => useTestServerConnection(), { wrapper });

        const res = await result.current.mutateAsync("test-server-uuid");

        expect(serversApi.testConnection).toHaveBeenCalledWith("test-server-uuid");
        expect(res.success).toBe(true);
        expect(res.latency_ms).toBe(24.5);
        expect(res.tools_count).toBe(2);
    });

    it("executes refreshTools mutation successfully", async () => {
        const mockTools = [
            {
                id: "test-server-uuid:calc",
                name: "calc",
                description: "Calculator",
                input_schema: {},
                server_id: "test-server-uuid",
                server_name: "test-server",
                availability_status: "AVAILABLE",
                last_discovered_at: "2026-10-24T15:00:00Z",
            },
        ];
        (serversApi.refreshTools as any).mockResolvedValue(mockTools);

        const { result } = renderHook(() => useRefreshServerTools(), { wrapper });

        const tools = await result.current.mutateAsync("test-server-uuid");

        expect(serversApi.refreshTools).toHaveBeenCalledWith("test-server-uuid");
        expect(tools.length).toBe(1);
        expect(tools[0].name).toBe("calc");
    });

    it("executes deleteServer mutation successfully and purges cache", async () => {
        (serversApi.delete as any).mockResolvedValue(undefined);

        const { result } = renderHook(() => useDeleteServer(), { wrapper });

        await result.current.mutateAsync("test-server-uuid");

        expect(serversApi.delete).toHaveBeenCalledWith("test-server-uuid");
    });
});
