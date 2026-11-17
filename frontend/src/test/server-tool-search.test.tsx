import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, waitFor, within } from "@testing-library/react";
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
    { name: "create_pull_request", description: "Open a new PR" },
    { name: "list_issues", description: "List issues in a repository" },
    { name: "merge_branch", description: "Merge a Pull Request into the base branch" },
    { name: "get_me", description: null },
].map((tool, index) => ({
    ...tool,
    id: `00000000-0000-4000-8000-00000000000${index}`,
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

const KEY_TOOLS: ApiKeyTool[] = TOOLS.map((tool) => ({ tool_id: tool.id, name: tool.name, description: tool.description, enabled: true }));

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

function shownToolNames(): string[] {
    const table = screen.getByTestId("server-tools-table");
    return within(table)
        .getAllByRole("link")
        .map((link) => link.textContent ?? "")
        .filter((text) => TOOLS.some((tool) => tool.name === text));
}

describe("Server detail tool search", () => {
    beforeEach(() => {
        vi.mocked(authApi.listApiKeys).mockReset().mockResolvedValue([API_KEY]);
        vi.mocked(authApi.listServerTools).mockReset().mockResolvedValue(KEY_TOOLS);
        vi.mocked(authApi.setToolEnabled).mockReset().mockResolvedValue({ tool_name: "merge_branch", enabled: false });
    });

    it("shows every tool and no count while the search is empty", async () => {
        await renderPage();

        expect(await screen.findByRole("searchbox", { name: "Search tools" })).toHaveValue("");
        expect(shownToolNames()).toEqual(TOOLS.map((tool) => tool.name));
        expect(screen.queryByText(/^Showing/)).not.toBeInTheDocument();
    });

    it("keeps tools whose name or description contains the text, ignoring case", async () => {
        const user = userEvent.setup();
        await renderPage();

        await user.type(await screen.findByRole("searchbox", { name: "Search tools" }), "PULL");

        // create_pull_request by name, merge_branch by its description ("Pull Request")
        expect(shownToolNames()).toEqual(["create_pull_request", "merge_branch"]);
        expect(screen.getByText("Showing 2 of 4 tools")).toBeInTheDocument();
    });

    it("finds a tool by a word only its description contains", async () => {
        const user = userEvent.setup();
        await renderPage();

        await user.type(await screen.findByRole("searchbox", { name: "Search tools" }), "repository");

        expect(shownToolNames()).toEqual(["list_issues"]);
    });

    it("shows an empty state when nothing matches, and clearing restores the list", async () => {
        const user = userEvent.setup();
        await renderPage();
        const search = await screen.findByRole("searchbox", { name: "Search tools" });

        await user.type(search, "zzz");
        expect(screen.getByText("No tools match ‘zzz’")).toBeInTheDocument();
        expect(screen.queryByTestId("server-tools-table")).not.toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Clear search" }));
        expect(search).toHaveValue("");
        expect(shownToolNames()).toHaveLength(TOOLS.length);
    });

    it("keeps the visibility switch working on a filtered row", async () => {
        const user = userEvent.setup();
        await renderPage();

        const select = await screen.findByRole("combobox", { name: "Visibility for API key" });
        await waitFor(() => expect(select).toBeEnabled());
        await user.click(select);
        await user.click(await screen.findByRole("option", { name: "claude-desktop" }));
        await user.type(screen.getByRole("searchbox", { name: "Search tools" }), "merge");

        const [toggle] = await screen.findAllByRole("switch", { name: "Visible to claude-desktop" });
        await waitFor(() => expect(toggle).toBeEnabled());
        await user.click(toggle);

        await waitFor(() => expect(authApi.setToolEnabled).toHaveBeenCalledWith(KEY_ID, SERVER_ID, "merge_branch", false));
    });
});
