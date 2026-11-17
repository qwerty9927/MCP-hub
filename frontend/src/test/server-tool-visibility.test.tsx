import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React, { Suspense } from "react";
import ServerDetailPage from "@/app/(dashboard)/servers/[serverId]/page";
import { authApi } from "@/lib/api";
import { ApiKeyRead, ApiKeyTool } from "@/types";

const SERVER_ID = "0b7f6c1e-5d2a-4c8e-9f31-2a6d4e8b7c90";
const KEY_ID = "5c1d2e3f-4a5b-4c6d-8e7f-9a0b1c2d3e4f";

const mutation = () => ({ isPending: false, mutate: vi.fn(), mutateAsync: vi.fn() });

const TOOLS = [
    { id: "8e693368-04c9-44b3-b554-eec9de50cb23", name: "create_issue" },
    { id: "1f2e3d4c-5b6a-4978-8695-a4b3c2d1e0f9", name: "delete_repo" },
].map((tool) => ({
    ...tool,
    description: null,
    input_schema: { type: "object", properties: {}, required: [] },
    server_id: SERVER_ID,
    server_name: "github",
    availability_status: "AVAILABLE",
    last_discovered_at: "2026-11-16T10:00:00Z",
}));

const API_KEY: ApiKeyRead = {
    id: KEY_ID,
    name: "claude-desktop",
    key_prefix: "mcp_abc",
    created_at: "2026-11-16T10:00:00Z",
};

const KEY_TOOLS: ApiKeyTool[] = [
    { tool_id: TOOLS[0].id, name: "create_issue", description: null, enabled: true },
    { tool_id: TOOLS[1].id, name: "delete_repo", description: null, enabled: false },
];

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn() }),
    usePathname: () => `/servers/${SERVER_ID}`,
}));

vi.mock("@/features/executions/hooks/use-executions", () => ({
    useExecutions: () => ({ data: { items: [] }, isLoading: false }),
}));

vi.mock("@/lib/api", () => ({
    authApi: {
        listApiKeys: vi.fn(),
        listServerTools: vi.fn(),
        setToolEnabled: vi.fn(),
    },
}));

vi.mock("@/features/servers/hooks/use-servers", () => ({
    SERVERS_QUERY_KEY: ["servers"],
    useServer: () => ({
        data: {
            id: SERVER_ID,
            name: "github",
            description: null,
            transport: "stdio",
            enabled: true,
            health_status: "HEALTHY",
            connection_config: { command: "npx", args: [] },
            created_at: "2026-11-16T10:00:00Z",
            updated_at: "2026-11-16T10:00:00Z",
        },
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
    }),
    useServerTools: () => ({ data: { items: TOOLS }, isLoading: false }),
    useConnectServer: () => mutation(),
    useDisconnectServer: () => mutation(),
    useTestServerConnection: () => mutation(),
    useRefreshServerTools: () => mutation(),
    useDeleteServer: () => mutation(),
}));

async function renderPage() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    await act(async () => {
        render(
            <QueryClientProvider client={queryClient}>
                <Suspense fallback={<div>Loading page...</div>}>
                    <ServerDetailPage params={Promise.resolve({ serverId: SERVER_ID })} />
                </Suspense>
            </QueryClientProvider>
        );
    });
}

async function chooseKey(user: ReturnType<typeof userEvent.setup>) {
    const select = await screen.findByRole("combobox", { name: "Visibility for API key" });
    await waitFor(() => expect(select).toBeEnabled());
    await user.click(select);
    await user.click(await screen.findByRole("option", { name: "claude-desktop" }));
}

describe("Server detail per-API-key tool visibility", () => {
    beforeEach(() => {
        vi.mocked(authApi.listApiKeys).mockReset().mockResolvedValue([API_KEY]);
        vi.mocked(authApi.listServerTools).mockReset().mockResolvedValue(KEY_TOOLS);
        vi.mocked(authApi.setToolEnabled).mockReset().mockResolvedValue({ tool_name: "create_issue", enabled: false });
    });

    it("shows no switches and loads nothing until a key is chosen", async () => {
        await renderPage();

        expect(await screen.findByRole("combobox", { name: "Visibility for API key" })).toHaveTextContent("No key selected");
        expect(screen.queryAllByRole("switch")).toHaveLength(0);
        expect(screen.queryByRole("columnheader", { name: "Visible" })).not.toBeInTheDocument();
        expect(screen.queryByText("Hidden for this key")).not.toBeInTheDocument();
        expect(authApi.listServerTools).not.toHaveBeenCalled();
    });

    it("loads the chosen key's settings and marks the hidden tool", async () => {
        const user = userEvent.setup();
        await renderPage();
        await chooseKey(user);

        await waitFor(() => expect(authApi.listServerTools).toHaveBeenCalledWith(KEY_ID, SERVER_ID, expect.anything()));
        const switches = await screen.findAllByRole("switch", { name: "Visible to claude-desktop" });
        expect(switches).toHaveLength(2);
        await waitFor(() => expect(switches[1]).toHaveAttribute("aria-checked", "false"));
        expect(switches[0]).toHaveAttribute("aria-checked", "true");

        const badge = screen.getByText("Hidden for this key");
        expect(badge.closest("tr")).toHaveTextContent("delete_repo");
        expect(badge.closest("tr")).toHaveAttribute("data-hidden", "true");
        expect(screen.getAllByText("Hidden for this key")).toHaveLength(1);
    });

    it("toggling a switch calls the client with the key, server and tool", async () => {
        const user = userEvent.setup();
        await renderPage();
        await chooseKey(user);

        const switches = await screen.findAllByRole("switch", { name: "Visible to claude-desktop" });
        await waitFor(() => expect(switches[0]).toBeEnabled());
        // The refetch after the change returns what the server now stores.
        vi.mocked(authApi.listServerTools).mockResolvedValue(KEY_TOOLS.map((tool) => ({ ...tool, enabled: false })));
        await user.click(switches[0]);

        expect(authApi.setToolEnabled).toHaveBeenCalledWith(KEY_ID, SERVER_ID, "create_issue", false);
        // Optimistic: the row is hidden at once.
        await waitFor(() => expect(screen.getAllByText("Hidden for this key")).toHaveLength(2));
    });

    it("links to the API keys page when the account has no keys", async () => {
        vi.mocked(authApi.listApiKeys).mockResolvedValue([]);
        await renderPage();

        expect(await screen.findByRole("link", { name: "Create one on the API keys page" })).toHaveAttribute("href", "/settings");
        expect(screen.queryByRole("combobox", { name: "Visibility for API key" })).not.toBeInTheDocument();
    });
});
