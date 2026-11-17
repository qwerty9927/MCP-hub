import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import React, { Suspense } from "react";
import ServerDetailPage from "@/app/(dashboard)/servers/[serverId]/page";
import { historyServerHref } from "@/lib/server-links";

const SERVER_ID = "0b7f6c1e-5d2a-4c8e-9f31-2a6d4e8b7c90";
const nav = vi.hoisted(() => ({ search: "" }));
const notFound = Object.assign(new Error("Server with id not found"), { status: 404 });
const mutation = () => ({ isPending: false, mutate: vi.fn(), mutateAsync: vi.fn() });

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn() }),
    usePathname: () => `/servers/${SERVER_ID}`,
    useSearchParams: () => new URLSearchParams(nav.search),
}));
vi.mock("@/features/auth/hooks/use-auth", () => ({ useApiKeys: () => ({ data: [], isLoading: false }) }));
vi.mock("@/features/servers/hooks/use-api-key-tools", () => ({
    useApiKeyServerTools: () => ({ data: undefined, isLoading: false }),
    useSetApiKeyToolEnabled: () => mutation(),
}));
vi.mock("@/features/executions/hooks/use-executions", () => ({ useExecutions: () => ({ data: { items: [] }, isLoading: false }) }));
vi.mock("@/features/servers/hooks/use-servers", () => ({
    useServer: () => ({ data: undefined, isLoading: false, isError: true, error: notFound, refetch: vi.fn() }),
    useServerTools: () => ({ data: undefined, isLoading: false }),
    useConnectServer: () => mutation(),
    useDisconnectServer: () => mutation(),
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

describe("Server page for a server deleted since it ran", () => {
    beforeEach(() => {
        nav.search = "";
    });

    it("history links carry where they came from and the stored name", () => {
        expect(historyServerHref(SERVER_ID, "Math Server")).toBe(`/servers/${SERVER_ID}?from=history&name=Math+Server`);
    });

    it("says the server has been deleted when opened from history", async () => {
        nav.search = new URL(historyServerHref(SERVER_ID, "Math Server"), "http://x").search;
        await renderPage();

        const notice = await screen.findByTestId("deleted-server-notice");
        expect(notice).toHaveTextContent("Math Server has been deleted");
        expect(notice).toHaveTextContent("Its execution history is kept");
        expect(screen.getByRole("link", { name: /Back to Execution History/ })).toHaveAttribute("href", "/executions");
        expect(screen.queryByText("Server Not Found")).not.toBeInTheDocument();
    });

    it("keeps the generic not-found error for a 404 reached any other way", async () => {
        await renderPage();
        expect(await screen.findByText("Server Not Found")).toBeInTheDocument();
        expect(screen.queryByTestId("deleted-server-notice")).not.toBeInTheDocument();
    });
});
