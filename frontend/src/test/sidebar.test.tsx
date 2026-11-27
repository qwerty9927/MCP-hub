import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const nav = vi.hoisted(() => ({ pathname: "/servers" }));

vi.mock("next/navigation", () => ({
    usePathname: () => nav.pathname,
}));

const api = vi.hoisted(() => ({
    health: vi.fn(async () => ({ status: "ok", version: "0.1.0", timestamp: "2026-11-27T10:00:00Z" })),
    list: vi.fn(async () => ({
        items: [
            { id: "s1", name: "github-server" },
            { id: "s2", name: "postgres-mcp" },
        ],
        total: 9,
        page: 1,
        page_size: 6,
        total_pages: 2,
    })),
}));

vi.mock("@/lib/api", () => ({ systemApi: { health: api.health }, serversApi: { list: api.list } }));

import { Sidebar, activeNavHref, NAV_GROUPS, NAV_ITEMS } from "@/components/layout/Sidebar";

function renderSidebar(props: React.ComponentProps<typeof Sidebar> = {}) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={client}>
            <Sidebar {...props} />
        </QueryClientProvider>
    );
}

beforeEach(() => {
    nav.pathname = "/servers";
    api.list.mockClear();
});

describe("Sidebar navigation", () => {
    it("groups the navigation into Registry, Operate and Manage", () => {
        expect(NAV_GROUPS.map((group) => group.label)).toEqual([null, "Registry", "Operate", "Manage"]);
        renderSidebar();

        const main = screen.getByRole("navigation", { name: "Main" });
        for (const label of ["Registry", "Operate", "Manage"]) {
            expect(within(main).getByText(label)).toBeInTheDocument();
        }
        for (const item of NAV_ITEMS) {
            expect(within(main).getByRole("link", { name: new RegExp(item.name) })).toHaveAttribute("href", item.href);
        }
        expect(screen.getByRole("link", { name: "API Keys" })).toHaveAttribute("href", "/settings/api-keys");
        expect(screen.getByRole("link", { name: "Discovery" })).toHaveAttribute("href", "/discovery");
    });

    it("shows the hub identity and quick search", async () => {
        const onOpenSearch = vi.fn();
        renderSidebar({ onOpenSearch });

        expect(screen.getByText("MCP Hub")).toBeInTheDocument();
        expect(screen.getByText("localhost:8000")).toBeInTheDocument();

        screen.getByRole("button", { name: /Quick search/ }).click();
        expect(onOpenSearch).toHaveBeenCalled();
        expect(await screen.findByText("v0.1.0")).toBeInTheDocument();
    });

    it("marks the current section and lists servers under MCP Servers on a server page", async () => {
        nav.pathname = "/servers/s2";
        renderSidebar();

        expect(await screen.findByRole("link", { name: "postgres-mcp" })).toHaveAttribute("aria-current", "page");
        expect(screen.getByRole("link", { name: "github-server" })).not.toHaveAttribute("aria-current");
        expect(screen.getByRole("link", { name: "All 9 servers" })).toHaveAttribute("href", "/servers");
    });

    it("does not load the server list outside the servers pages", () => {
        nav.pathname = "/tools";
        renderSidebar();

        expect(screen.getByRole("link", { name: "Tool Catalog" })).toHaveAttribute("aria-current", "page");
        expect(api.list).not.toHaveBeenCalled();
    });

    it("picks the most specific nav item for a path", () => {
        expect(activeNavHref("/")).toBe("/overview");
        expect(activeNavHref("/settings")).toBe("/settings");
        expect(activeNavHref("/settings/api-keys")).toBe("/settings/api-keys");
        expect(activeNavHref("/settings/members")).toBe("/settings");
        expect(activeNavHref("/servers/abc/edit")).toBe("/servers");
        expect(activeNavHref("/unknown")).toBeNull();
    });
});
