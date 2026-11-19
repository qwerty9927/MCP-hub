import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import React, { Suspense } from "react";
import ServerDetailPage from "@/app/(dashboard)/servers/[serverId]/page";

const SERVER_ID = "0b7f6c1e-5d2a-4c8e-9f31-2a6d4e8b7c90";

const mutation = (isPending = false) => ({ isPending, mutate: vi.fn(), mutateAsync: vi.fn() });
const state = { refreshPending: false };

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

vi.mock("@/features/servers/hooks/use-servers", () => ({
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
    useServerTools: () => ({
        data: {
            items: [
                {
                    id: "8e693368-04c9-44b3-b554-eec9de50cb23",
                    name: "add_comment_to_pending_review",
                    description: "Add review comment to the requester's latest pending pull request review.",
                    input_schema: { type: "object", properties: { body: { type: "string" } }, required: ["body"] },
                    server_id: SERVER_ID,
                    server_name: "github",
                    availability_status: "AVAILABLE",
                    last_discovered_at: "2026-11-16T10:00:00Z",
                },
            ],
        },
        isLoading: false,
    }),
    useTestServerConnection: () => mutation(),
    useRefreshServerTools: () => mutation(state.refreshPending),
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

describe("Server detail tools table while tools are refreshed", () => {
    beforeEach(() => {
        state.refreshPending = false;
    });

    it("keeps the tool list usable when nothing is refreshing", async () => {
        await renderPage();

        const table = screen.getByTestId("server-tools-table");
        expect(table).not.toHaveAttribute("inert");
        expect(table.parentElement).toHaveAttribute("aria-busy", "false");
        expect(screen.queryByText("Refreshing tools…")).not.toBeInTheDocument();
        expect(screen.getByRole("link", { name: "add_comment_to_pending_review" })).toBeInTheDocument();
    });

    it("disables the old tool list while Refresh Tools is running", async () => {
        state.refreshPending = true;
        await renderPage();

        const table = screen.getByTestId("server-tools-table");
        expect(table).toHaveAttribute("inert");
        expect(table).toHaveClass("pointer-events-none");
        expect(table.parentElement).toHaveAttribute("aria-busy", "true");
        expect(screen.getByRole("status")).toHaveTextContent("Refreshing tools…");
    });
});
