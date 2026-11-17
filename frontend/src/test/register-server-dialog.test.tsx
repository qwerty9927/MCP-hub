import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RegisterServerButton } from "@/features/servers/components/RegisterServerButton";
import { OAuthReconnectButton } from "@/features/servers/components/OAuthReconnectButton";
import { oauthApi, serversApi } from "@/lib/api";
import { OAuthProvider, ServerRead } from "@/types";

const push = vi.fn();

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push, replace: vi.fn(), back: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
    oauthApi: {
        providers: vi.fn(),
        connect: vi.fn(),
        reconnect: vi.fn(),
    },
    serversApi: {
        getById: vi.fn(),
        create: vi.fn(),
    },
}));

vi.mock("sonner", () => ({
    toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

const PROVIDERS: OAuthProvider[] = [
    {
        id: "linear",
        name: "Linear",
        description: "Issues, projects and cycles",
        category: "Project management",
        mcp_url: "https://mcp.linear.app/mcp",
        docs_url: "https://linear.app/docs/mcp",
        available: true,
        connected_count: 0,
    },
    {
        id: "notion",
        name: "Notion",
        description: "Pages, databases and comments",
        category: "Productivity",
        mcp_url: "https://mcp.notion.com/mcp",
        docs_url: "https://developers.notion.com/docs/mcp",
        available: true,
        connected_count: 1,
    },
    {
        id: "github",
        name: "GitHub",
        description: "Repositories, issues and pull requests",
        category: "Developer tools",
        mcp_url: "https://api.githubcopilot.com/mcp/",
        docs_url: "https://github.com/github/github-mcp-server",
        available: false,
        client_env: "OAUTH_CLIENTS",
        connected_count: 0,
    },
    {
        id: "sentry",
        name: "Sentry",
        description: "Errors, issues and releases",
        category: "Monitoring",
        mcp_url: "https://mcp.sentry.dev/mcp",
        docs_url: "https://docs.sentry.io/product/sentry-mcp/",
        available: true,
        connected_count: 0,
    },
];

const AUTH_URL = "https://linear.app/oauth/authorize?state=abc";

const SERVER: ServerRead = {
    id: "srv-1",
    name: "Linear",
    description: null,
    transport: "streamable-http",
    connection_config: { url: "https://mcp.linear.app/mcp" },
    enabled: true,
    health_status: "HEALTHY",
    discovered_tool_count: 24,
    auth_type: "oauth",
    oauth_provider_id: "linear",
    created_at: "2026-11-17T10:00:00Z",
    updated_at: "2026-11-17T10:00:00Z",
};

interface FakePopup {
    closed: boolean;
    close: ReturnType<typeof vi.fn>;
    focus: ReturnType<typeof vi.fn>;
    location: { href: string };
}

function fakePopup(): FakePopup {
    return { closed: false, close: vi.fn(), focus: vi.fn(), location: { href: "" } };
}

function renderWithClient(ui: React.ReactElement) {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

async function openDialog() {
    const user = userEvent.setup();
    renderWithClient(<RegisterServerButton />);
    await user.click(screen.getByRole("button", { name: "Register Server" }));
    const dialog = await screen.findByRole("dialog", { name: "Register MCP server" });
    await within(dialog).findByRole("group", { name: "Providers" });
    return { user, dialog };
}

function providerNames(dialog: HTMLElement): string[] {
    const grid = within(dialog).queryByRole("group", { name: "Providers" });
    if (!grid) return [];
    return Array.from(grid.querySelectorAll<HTMLElement>("[data-provider-id]")).map((card) => card.dataset.providerId as string);
}

function postFromPopup(data: unknown, origin = window.location.origin) {
    act(() => {
        window.dispatchEvent(new MessageEvent("message", { data, origin }));
    });
}

describe("RegisterServerDialog", () => {
    let openSpy: ReturnType<typeof vi.fn>;

    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(oauthApi.providers).mockResolvedValue(PROVIDERS);
        vi.mocked(oauthApi.connect).mockResolvedValue({ authorization_url: AUTH_URL, state: "abc" });
        vi.mocked(serversApi.getById).mockResolvedValue(SERVER);
        openSpy = vi.fn(() => fakePopup());
        window.open = openSpy as unknown as typeof window.open;
    });

    it("focuses the search box and lists every provider", async () => {
        const { dialog } = await openDialog();
        expect(within(dialog).getByRole("searchbox", { name: "Search providers" })).toHaveFocus();
        expect(providerNames(dialog)).toEqual(["linear", "notion", "github", "sentry"]);
    });

    it("filters on name, description, category and host as the user types, highlighting the match", async () => {
        const { user, dialog } = await openDialog();
        const search = within(dialog).getByRole("searchbox", { name: "Search providers" });

        await user.type(search, "LIN");
        expect(providerNames(dialog)).toEqual(["linear"]);
        expect(within(dialog).getByText("Lin", { selector: "mark" })).toBeInTheDocument();

        await user.clear(search);
        await user.type(search, "databases");
        expect(providerNames(dialog)).toEqual(["notion"]);

        await user.clear(search);
        await user.type(search, "monitoring");
        expect(providerNames(dialog)).toEqual(["sentry"]);

        await user.clear(search);
        await user.type(search, "githubcopilot");
        expect(providerNames(dialog)).toEqual(["github"]);
    });

    it("filters by category chip", async () => {
        const { user, dialog } = await openDialog();
        await user.click(within(dialog).getByRole("button", { name: "Productivity" }));
        expect(providerNames(dialog)).toEqual(["notion"]);
        expect(within(dialog).getByRole("button", { name: "Productivity" })).toHaveAttribute("aria-pressed", "true");

        await user.click(within(dialog).getByRole("button", { name: "All" }));
        expect(providerNames(dialog)).toHaveLength(PROVIDERS.length);
    });

    it("shows an empty state with a manual option when nothing matches", async () => {
        const { user, dialog } = await openDialog();
        await user.type(within(dialog).getByRole("searchbox", { name: "Search providers" }), "zzz");

        const empty = within(dialog).getByTestId("provider-empty-state");
        expect(empty).toHaveTextContent("No provider matches “zzz”");
        await user.click(within(empty).getByRole("button", { name: "Configure manually" }));
        expect(push).toHaveBeenCalledWith("/servers/new");
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    });

    it("shows unconfigured providers as Needs setup and doesn't connect them", async () => {
        const { user, dialog } = await openDialog();
        const github = dialog.querySelector<HTMLElement>('[data-provider-id="github"]') as HTMLElement;

        expect(github).toHaveAttribute("aria-disabled", "true");
        expect(within(github).getByText("Needs setup")).toBeInTheDocument();

        await user.click(github);
        expect(oauthApi.connect).not.toHaveBeenCalled();
        expect(openSpy).not.toHaveBeenCalled();
        expect(within(dialog).getByRole("group", { name: "Providers" })).toBeInTheDocument();
    });

    it("marks providers already connected", async () => {
        const { dialog } = await openDialog();
        const notion = dialog.querySelector<HTMLElement>('[data-provider-id="notion"]') as HTMLElement;
        expect(within(notion).getByText("Connected")).toBeInTheDocument();
    });

    it("Configure manually closes the dialog and opens the full-page form instead of showing it in the dialog", async () => {
        const { user, dialog } = await openDialog();
        await user.click(within(dialog).getByRole("button", { name: /Not listed\? Configure manually/ }));

        expect(push).toHaveBeenCalledWith("/servers/new");
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
        expect(screen.queryByText("Server Information")).not.toBeInTheDocument();
    });

    it("moves through the grid with the arrow keys (roving tabindex)", async () => {
        const { user, dialog } = await openDialog();
        const cards = () => Array.from(dialog.querySelectorAll<HTMLElement>("[data-provider-id]"));

        expect(cards().map((card) => card.tabIndex)).toEqual([0, -1, -1, -1]);
        await user.keyboard("{ArrowDown}");
        expect(cards()[0]).toHaveFocus();
        await user.keyboard("{ArrowRight}");
        expect(cards()[1]).toHaveFocus();
        expect(cards().map((card) => card.tabIndex)).toEqual([-1, 0, -1, -1]);
        await user.keyboard("{End}");
        expect(cards()[3]).toHaveFocus();
    });

    it("signs in through the popup and shows the connected server on success", async () => {
        const popup = fakePopup();
        openSpy.mockReturnValue(popup);
        const { user, dialog } = await openDialog();

        await user.click(dialog.querySelector('[data-provider-id="linear"]') as HTMLElement);

        expect(openSpy).toHaveBeenCalledTimes(1);
        expect(oauthApi.connect).toHaveBeenCalledWith({ provider_id: "linear" });
        expect(await within(dialog).findByText("Finish signing in to Linear in the popup window")).toBeInTheDocument();
        expect(popup.location.href).toBe(AUTH_URL);

        postFromPopup({ type: "mcp-hub-oauth", status: "success", server_id: "srv-1" });

        expect(await within(dialog).findByText(/Linear connected/)).toBeInTheDocument();
        await waitFor(() => expect(within(dialog).getByTestId("oauth-connect-panel")).toHaveTextContent("24 tools discovered"));
        expect(serversApi.getById).toHaveBeenCalledWith("srv-1", expect.anything());

        await user.click(within(dialog).getByRole("button", { name: "Open server" }));
        expect(push).toHaveBeenCalledWith("/servers/srv-1");
    });

    it("names a second connection to the same provider", async () => {
        const { user, dialog } = await openDialog();
        await user.click(dialog.querySelector('[data-provider-id="notion"]') as HTMLElement);
        expect(oauthApi.connect).toHaveBeenCalledWith({ provider_id: "notion", name: "Notion 2" });
    });

    it("shows the error from the popup and can try again", async () => {
        const { user, dialog } = await openDialog();
        await user.click(dialog.querySelector('[data-provider-id="linear"]') as HTMLElement);
        await within(dialog).findByText("Finish signing in to Linear in the popup window");

        postFromPopup({ type: "mcp-hub-oauth", status: "error", error: "access_denied" });

        expect(await within(dialog).findByText("Couldn't connect Linear")).toBeInTheDocument();
        const message = within(dialog).getByText("Access was declined on the provider's sign-in page.");
        expect(message).toHaveClass("text-red-700");
        expect(within(dialog).getByRole("button", { name: "Configure manually" })).toBeInTheDocument();

        await user.click(within(dialog).getByRole("button", { name: "Try again" }));
        expect(oauthApi.connect).toHaveBeenCalledTimes(2);
        expect(await within(dialog).findByText("Finish signing in to Linear in the popup window")).toBeInTheDocument();
    });

    it("shows a start failure from the backend as an error", async () => {
        vi.mocked(oauthApi.connect).mockRejectedValue(new Error("Provider discovery failed"));
        const popup = fakePopup();
        openSpy.mockReturnValue(popup);
        const { user, dialog } = await openDialog();

        await user.click(dialog.querySelector('[data-provider-id="linear"]') as HTMLElement);

        expect(await within(dialog).findByText("Provider discovery failed")).toBeInTheDocument();
        expect(popup.close).toHaveBeenCalled();

        // From the error, the manual fallback is the full-page form too.
        await user.click(within(dialog).getByRole("button", { name: "Configure manually" }));
        expect(push).toHaveBeenCalledWith("/servers/new");
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    });

    it("ignores messages from another origin or of another type", async () => {
        const { user, dialog } = await openDialog();
        await user.click(dialog.querySelector('[data-provider-id="linear"]') as HTMLElement);
        await within(dialog).findByText("Finish signing in to Linear in the popup window");

        postFromPopup({ type: "mcp-hub-oauth", status: "success", server_id: "srv-evil" }, "https://evil.example");
        postFromPopup({ type: "something-else", status: "success", server_id: "srv-1" });
        postFromPopup("mcp-hub-oauth");

        expect(within(dialog).getByTestId("oauth-connect-panel")).toHaveAttribute("data-status", "waiting");
        expect(serversApi.getById).not.toHaveBeenCalled();
    });

    it("Cancel closes the popup and returns to the providers", async () => {
        const popup = fakePopup();
        openSpy.mockReturnValue(popup);
        const { user, dialog } = await openDialog();
        await user.click(dialog.querySelector('[data-provider-id="linear"]') as HTMLElement);
        await within(dialog).findByText("Finish signing in to Linear in the popup window");

        await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
        expect(popup.close).toHaveBeenCalled();
        expect(within(dialog).getByRole("searchbox", { name: "Search providers" })).toBeInTheDocument();
    });

    describe("when the popup is blocked", () => {
        const originalLocation = window.location;
        const assign = vi.fn();

        beforeEach(() => {
            Object.defineProperty(window, "location", {
                configurable: true,
                value: { ...originalLocation, origin: originalLocation.origin, href: originalLocation.href, assign },
            });
        });

        afterEach(() => {
            Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
        });

        it("offers to continue the sign-in in this tab", async () => {
            openSpy.mockReturnValue(null);
            const { user, dialog } = await openDialog();
            await user.click(dialog.querySelector('[data-provider-id="linear"]') as HTMLElement);

            expect(await within(dialog).findByText("Your browser blocked the sign-in popup")).toBeInTheDocument();
            await user.click(within(dialog).getByRole("button", { name: "Continue in this tab" }));
            expect(assign).toHaveBeenCalledWith(AUTH_URL);
        });

        it("can reopen the popup once popups are allowed", async () => {
            openSpy.mockReturnValueOnce(null);
            const { user, dialog } = await openDialog();
            await user.click(dialog.querySelector('[data-provider-id="linear"]') as HTMLElement);
            await within(dialog).findByText("Your browser blocked the sign-in popup");

            const popup = fakePopup();
            openSpy.mockReturnValueOnce(popup);
            await user.click(within(dialog).getByRole("button", { name: "Reopen popup" }));

            expect(openSpy).toHaveBeenLastCalledWith(AUTH_URL, expect.any(String), expect.any(String));
            expect(await within(dialog).findByText("Finish signing in to Linear in the popup window")).toBeInTheDocument();
        });
    });
});

describe("OAuthReconnectButton", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(oauthApi.providers).mockResolvedValue(PROVIDERS);
        vi.mocked(oauthApi.reconnect).mockResolvedValue({ authorization_url: AUTH_URL, state: "def" });
    });

    it("starts a new sign-in for the server in a popup", async () => {
        const popup = fakePopup();
        window.open = vi.fn(() => popup) as unknown as typeof window.open;
        const user = userEvent.setup();
        renderWithClient(<OAuthReconnectButton server={{ ...SERVER, health_status: "NEEDS_AUTH" }} />);

        await user.click(screen.getByRole("button", { name: "Reconnect" }));

        expect(oauthApi.reconnect).toHaveBeenCalledWith("srv-1");
        const dialog = await screen.findByRole("dialog", { name: "Reconnect Linear" });
        expect(await within(dialog).findByText("Finish signing in to Linear in the popup window")).toBeInTheDocument();
        expect(popup.location.href).toBe(AUTH_URL);

        postFromPopup({ type: "mcp-hub-oauth", status: "success", server_id: "srv-1" });
        expect(await within(dialog).findByText(/Linear connected/)).toBeInTheDocument();
    });
});
