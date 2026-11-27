import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const router = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/overview" }));

const api = vi.hoisted(() => ({
    servers: vi.fn(async () => ({ items: [{ id: "s1", name: "github-server", transport: "stdio", discovered_tool_count: 15 }], total: 1 })),
    tools: vi.fn(async () => ({ items: [{ id: "s1:search_issues", name: "search_issues", server_name: "github-server" }], total: 1 })),
    executions: vi.fn(async () => ({ items: [], total: 0 })),
}));
vi.mock("@/lib/api", () => ({
    serversApi: { list: api.servers },
    toolsApi: { list: api.tools },
    executionsApi: { list: api.executions },
}));

// The shell's other parts are covered elsewhere; here only the ⌘K wiring matters.
vi.mock("@/components/layout/AuthGuard", () => ({ AuthGuard: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/layout/Sidebar", () => ({ Sidebar: () => null }));
vi.mock("@/components/layout/Header", () => ({ Header: () => null }));

import { QuickSearchDialog } from "@/components/layout/QuickSearchDialog";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { PREFERENCES_KEY } from "@/lib/preferences";
import { resetLocalStoreCache } from "@/lib/local-store";

function withQueries(ui: React.ReactElement) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
    window.localStorage.clear();
    resetLocalStoreCache();
    router.push.mockClear();
});

describe("Quick search", () => {
    it("searches servers, tools and executions and groups the results", async () => {
        withQueries(<QuickSearchDialog open onOpenChange={vi.fn()} />);

        await userEvent.type(screen.getByRole("combobox", { name: /Search servers, tools and executions/ }), "git");

        expect(await screen.findByRole("group", { name: "Servers" })).toBeInTheDocument();
        expect(screen.getByRole("group", { name: "Tools" })).toBeInTheDocument();
        // The first server is selected; the tool row also mentions github-server as its server.
        expect(screen.getByRole("option", { name: /^github-server/ })).toHaveAttribute("aria-selected", "true");
        expect(api.servers).toHaveBeenCalledWith(expect.objectContaining({ search: "git" }), expect.anything());
        expect(api.executions).toHaveBeenCalledWith(expect.objectContaining({ tool_name: "git" }), expect.anything());
    });

    it("moves with the arrow keys and opens the result with Enter", async () => {
        const onOpenChange = vi.fn();
        withQueries(<QuickSearchDialog open onOpenChange={onOpenChange} />);
        const input = screen.getByRole("combobox", { name: /Search servers, tools and executions/ });

        await userEvent.type(input, "search");
        await screen.findByRole("option", { name: /search_issues/ });
        await userEvent.keyboard("{ArrowDown}{Enter}");

        expect(router.push).toHaveBeenCalledWith("/tools/s1%3Asearch_issues");
        expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    it("offers recent pages before anything is typed", () => {
        window.localStorage.setItem(
            "mcp-hub:recents",
            JSON.stringify([{ section: "Servers", label: "postgres-mcp", href: "/servers/s2", at: 1 }])
        );
        withQueries(<QuickSearchDialog open onOpenChange={vi.fn()} />);

        expect(screen.getByRole("group", { name: "Recent" })).toBeInTheDocument();
        expect(screen.getByRole("option", { name: /postgres-mcp/ })).toBeInTheDocument();
    });

    it("opens with ⌘K, and not when keyboard shortcuts are off", async () => {
        const { unmount } = withQueries(
            <DashboardShell>
                <p>page</p>
            </DashboardShell>
        );
        act(() => {
            fireEvent.keyDown(window, { key: "k", metaKey: true });
        });
        expect(await screen.findByRole("combobox", { name: /Search servers, tools and executions/ })).toBeInTheDocument();
        unmount();

        window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify({ keyboardShortcuts: false }));
        resetLocalStoreCache();
        withQueries(
            <DashboardShell>
                <p>page</p>
            </DashboardShell>
        );
        act(() => {
            fireEvent.keyDown(window, { key: "k", ctrlKey: true });
        });
        expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    });
});
