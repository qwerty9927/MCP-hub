import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import React, { Suspense } from "react";
import ServerDetailPage from "@/app/(dashboard)/servers/[serverId]/page";

const SERVER_ID = "3c1d9a7e-2b4f-4e6a-8d0c-5f7b9e1a3c2d";

const mutation = () => ({ isPending: false, mutate: vi.fn(), mutateAsync: vi.fn() });
const state: { authType: "none" | "oauth"; health: string } = { authType: "none", health: "DISCONNECTED" };

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn() }),
    usePathname: () => `/servers/${SERVER_ID}`,
    useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/features/auth/hooks/use-auth", () => ({
    useApiKeys: () => ({ data: [], isLoading: false }),
}));

vi.mock("@/features/servers/hooks/use-api-key-tools", () => ({
    useApiKeyServerTools: () => ({ data: undefined, isLoading: false }),
    useSetApiKeyToolEnabled: () => mutation(),
}));

vi.mock("@/features/executions/hooks/use-executions", () => ({
    useExecutions: () => ({ data: { items: [] }, isLoading: false }),
}));

vi.mock("@/features/servers/hooks/use-oauth", () => ({
    useOAuthProviders: () => ({ data: [] }),
    useOAuthFlow: () => ({
        state: { status: "idle", authorizationUrl: null, serverId: null, error: null },
        reconnect: vi.fn(),
        reopen: vi.fn(),
        continueInTab: vi.fn(),
        reset: vi.fn(),
    }),
}));

vi.mock("@/features/servers/hooks/use-servers", () => ({
    useServer: () => ({
        data: {
            id: SERVER_ID,
            name: "atlassian",
            description: "Atlassian: Jira issues and Confluence pages",
            transport: "streamable-http",
            enabled: true,
            auth_type: state.authType,
            oauth_provider_id: state.authType === "oauth" ? "atlassian" : null,
            health_status: state.health,
            connection_config: { url: "https://mcp.atlassian.com/v1/mcp", headers: {} },
            created_at: "2026-11-18T10:00:00Z",
            updated_at: "2026-11-18T10:00:00Z",
        },
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
    }),
    useServerTools: () => ({ data: { items: [] }, isLoading: false }),
    useTestServerConnection: () => mutation(),
    useRefreshServerTools: () => mutation(),
    useDeleteServer: () => mutation(),
}));

async function renderPage() {
    await act(async () => {
        render(
            <Suspense fallback={<div>Loading page...</div>}>
                <ServerDetailPage params={Promise.resolve({ serverId: SERVER_ID })} />
            </Suspense>
        );
    });
}

describe("Server detail header actions", () => {
    beforeEach(() => {
        state.authType = "none";
        state.health = "DISCONNECTED";
    });

    // Refresh Tools opens the connection and re-syncs tools, tool calls connect on their own,
    // and only the Enabled switch stops a server being used, so there is no Connect or Disconnect.
    it.each([
        ["none", "HEALTHY"],
        ["none", "DISCONNECTED"],
        ["none", "UNHEALTHY"],
        ["oauth", "HEALTHY"],
        ["oauth", "DISCONNECTED"],
        ["oauth", "NEEDS_AUTH"],
    ] as const)("auth %s, health %s: no Connect or Disconnect; Refresh Tools and Test Connection remain", async (authType, health) => {
        state.authType = authType;
        state.health = health;
        await renderPage();

        expect(screen.queryByRole("button", { name: "Connect" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Disconnect" })).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Refresh Tools" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Test Connection" })).toBeInTheDocument();
    });

    it("has no Reconnect on a server without OAuth", async () => {
        await renderPage();
        expect(screen.queryByRole("button", { name: "Reconnect" })).not.toBeInTheDocument();
    });

    it("offers Reconnect on an OAuth server", async () => {
        state.authType = "oauth";
        state.health = "HEALTHY";
        await renderPage();
        expect(screen.getByRole("button", { name: "Reconnect" })).toBeInTheDocument();
    });
});
