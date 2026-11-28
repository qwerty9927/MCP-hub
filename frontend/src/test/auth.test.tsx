import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import React from "react";
import { AxiosError, AxiosHeaders } from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LoginForm } from "@/features/auth/components/LoginForm";
import { RegisterForm } from "@/features/auth/components/RegisterForm";
import { AppApiError } from "@/lib/errors";
import { AuthGuard } from "@/components/layout/AuthGuard";
import { ApiKeysCard, mcpClientConfig } from "@/features/auth/components/ApiKeysCard";
import { handleUnauthorized, refreshSession } from "@/lib/api-client";
import { AUTH_TOKEN_KEY, clearAuthToken, getAuthToken, loginPath, safeNextPath, setAuthToken } from "@/lib/auth-token";
import { authApi } from "@/lib/api";
import { useLogout } from "@/features/auth/hooks/use-auth";

const replace = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace, push: vi.fn() }),
    usePathname: () => "/servers",
    useSearchParams: () => searchParams,
}));

vi.mock("@/lib/api", () => ({
    authApi: {
        login: vi.fn(),
        register: vi.fn(),
        me: vi.fn(),
        listApiKeys: vi.fn(),
        createApiKey: vi.fn(),
        updateApiKey: vi.fn(),
        revokeApiKey: vi.fn(),
        logout: vi.fn(),
    },
}));

// AuthGuard tries the refresh token cookie before sending a tab without a token to login; never hit the network here.
vi.mock("@/lib/api-client", async (importOriginal) => ({
    ...(await importOriginal<typeof import("@/lib/api-client")>()),
    refreshSession: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

function renderWithClient(ui: React.ReactElement) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    searchParams = new URLSearchParams();
    vi.mocked(refreshSession).mockResolvedValue(null);
});

describe("auth token helpers", () => {
    it("only accepts same-site paths after login", () => {
        expect(safeNextPath("/sessions/abc")).toBe("/sessions/abc");
        expect(safeNextPath("https://evil.example")).toBe("/overview");
        expect(safeNextPath("//evil.example")).toBe("/overview");
        expect(safeNextPath(null)).toBe("/overview");
        expect(loginPath("/servers?page=2")).toBe("/login?next=%2Fservers%3Fpage%3D2");
        expect(loginPath("/login")).toBe("/login");
    });
});

describe("LoginForm", () => {
    it("stores the token and returns to the requested page", async () => {
        searchParams = new URLSearchParams("next=/sessions");
        vi.mocked(authApi.login).mockResolvedValue({ access_token: "jwt-123", token_type: "bearer", expires_in: 3600 });
        renderWithClient(<LoginForm />);

        fireEvent.change(screen.getByLabelText("Email"), { target: { value: "me@example.com" } });
        fireEvent.change(screen.getByLabelText("Password"), { target: { value: "s3cret-pass" } });
        fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

        await waitFor(() => expect(replace).toHaveBeenCalledWith("/sessions"));
        expect(authApi.login).toHaveBeenCalledWith({ email: "me@example.com", password: "s3cret-pass" });
        expect(getAuthToken()).toBe("jwt-123");
    });

    it("shows the server's error on bad credentials", async () => {
        vi.mocked(authApi.login).mockRejectedValue(new Error("Invalid email or password"));
        renderWithClient(<LoginForm />);

        fireEvent.change(screen.getByLabelText("Email"), { target: { value: "me@example.com" } });
        fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong" } });
        fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
        expect(getAuthToken()).toBeNull();
        expect(replace).not.toHaveBeenCalled();
    });

    it("shows how long to wait and blocks sign-in while rate limited", async () => {
        vi.useFakeTimers({ shouldAdvanceTime: true });
        try {
            vi.mocked(authApi.login).mockRejectedValue(
                new AppApiError("Too many failed attempts. Try again later.", "TooManyRequestsError", 429, undefined, undefined, 90)
            );
            renderWithClient(<LoginForm />);

            fireEvent.change(screen.getByLabelText("Email"), { target: { value: "me@example.com" } });
            fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong" } });
            fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

            expect(await screen.findByRole("alert")).toHaveTextContent("Too many attempts. Try again in 2 minutes.");
            expect(screen.getByRole("button", { name: "Sign in" })).toBeDisabled();

            await act(async () => {
                vi.advanceTimersByTime(91_000);
            });

            expect(screen.queryByRole("alert")).not.toBeInTheDocument();
            expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
        } finally {
            vi.useRealTimers();
        }
    });
});

describe("RegisterForm", () => {
    it("shows how long to wait after too many sign-ups from this address", async () => {
        vi.mocked(authApi.register).mockRejectedValue(
            new AppApiError("Too many attempts. Try again later.", "TooManyRequestsError", 429, undefined, undefined, 45)
        );
        renderWithClient(<RegisterForm />);

        fireEvent.change(screen.getByLabelText("Email"), { target: { value: "me@example.com" } });
        fireEvent.change(screen.getByLabelText("Password"), { target: { value: "s3cret-pass-123" } });
        fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "s3cret-pass-123" } });
        fireEvent.click(screen.getByRole("button", { name: "Create account" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Too many attempts. Try again in 45 seconds.");
        expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
    });
});

describe("AuthGuard", () => {
    it("redirects to login when there is no token", async () => {
        renderWithClient(
            <AuthGuard>
                <p>secret dashboard</p>
            </AuthGuard>
        );

        await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2Fservers"));
        expect(refreshSession).toHaveBeenCalled();
        expect(screen.queryByText("secret dashboard")).not.toBeInTheDocument();
    });

    it("stays signed in from the refresh cookie in a tab without a token", async () => {
        vi.mocked(refreshSession).mockImplementation(async () => {
            setAuthToken("jwt-from-cookie");
            return "jwt-from-cookie";
        });
        vi.mocked(authApi.me).mockResolvedValue({ id: "u1", email: "me@example.com", created_at: "2026-11-12T00:00:00Z" });

        renderWithClient(
            <AuthGuard>
                <p>secret dashboard</p>
            </AuthGuard>
        );

        expect(await screen.findByText("secret dashboard")).toBeInTheDocument();
        expect(replace).not.toHaveBeenCalled();
    });

    it("goes to login without trying the cookie when the token goes away after sign-in", async () => {
        setAuthToken("jwt-123");
        vi.mocked(authApi.me).mockResolvedValue({ id: "u1", email: "me@example.com", created_at: "2026-11-12T00:00:00Z" });
        renderWithClient(
            <AuthGuard>
                <p>secret dashboard</p>
            </AuthGuard>
        );
        await screen.findByText("secret dashboard");

        // Sign-out clears the token while the dashboard is still mounted; a refresh now would race POST /auth/logout.
        act(() => clearAuthToken());

        await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2Fservers"));
        expect(refreshSession).not.toHaveBeenCalled();
    });

    it("renders the dashboard once the account is confirmed", async () => {
        setAuthToken("jwt-123");
        vi.mocked(authApi.me).mockResolvedValue({ id: "u1", email: "me@example.com", created_at: "2026-11-12T00:00:00Z" });

        renderWithClient(
            <AuthGuard>
                <p>secret dashboard</p>
            </AuthGuard>
        );

        expect(await screen.findByText("secret dashboard")).toBeInTheDocument();
        expect(replace).not.toHaveBeenCalled();
    });

    it("signs out when the token is rejected", async () => {
        setAuthToken("expired");
        vi.mocked(authApi.me).mockRejectedValue(new Error("Invalid or expired token"));

        renderWithClient(
            <AuthGuard>
                <p>secret dashboard</p>
            </AuthGuard>
        );

        await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2Fservers"));
        expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
    });
});

describe("401 interceptor", () => {
    function axios401(url: string) {
        const config = { url, headers: new AxiosHeaders() };
        return new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, {
            status: 401,
            statusText: "Unauthorized",
            headers: {},
            config,
            data: {},
        });
    }

    it("clears the token on a 401 from a protected endpoint", () => {
        sessionStorage.setItem(AUTH_TOKEN_KEY, "jwt-123");
        const assign = vi.fn();
        vi.stubGlobal("location", { ...window.location, pathname: "/servers", search: "", assign });

        handleUnauthorized(axios401("/servers"));

        expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
        expect(assign).toHaveBeenCalledWith("/login?next=%2Fservers");
        vi.unstubAllGlobals();
    });

    it("leaves a failed login alone", () => {
        sessionStorage.setItem(AUTH_TOKEN_KEY, "jwt-123");

        handleUnauthorized(axios401("/auth/login"));

        expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe("jwt-123");
    });
});

describe("useLogout", () => {
    function SignOut() {
        const logout = useLogout();
        return <button onClick={() => void logout()}>Sign out</button>;
    }

    it("revokes the refresh token on the server and clears the tab's token", async () => {
        setAuthToken("jwt-123");
        vi.mocked(authApi.logout).mockResolvedValue(undefined);
        renderWithClient(<SignOut />);

        fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

        expect(authApi.logout).toHaveBeenCalledTimes(1);
        expect(getAuthToken()).toBeNull();
    });

    it("still signs out locally when the server cannot be reached", async () => {
        setAuthToken("jwt-123");
        vi.mocked(authApi.logout).mockRejectedValue(new Error("Network Error"));
        renderWithClient(<SignOut />);

        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
        });

        expect(getAuthToken()).toBeNull();
    });
});

describe("ApiKeysCard", () => {
    it("lists keys and revokes one", async () => {
        vi.mocked(authApi.listApiKeys).mockResolvedValue([
            {
                id: "k1",
                name: "laptop Claude",
                key_prefix: "mhk_abcd",
                created_at: "2026-11-12T00:00:00Z",
                last_used_at: null,
                revoked_at: null,
            },
            {
                id: "k2",
                name: "old script",
                key_prefix: "mhk_wxyz",
                created_at: "2026-11-01T00:00:00Z",
                revoked_at: "2026-11-05T00:00:00Z",
            },
        ]);
        vi.mocked(authApi.revokeApiKey).mockResolvedValue(undefined);
        renderWithClient(<ApiKeysCard />);

        expect(await screen.findByText("laptop Claude")).toBeInTheDocument();
        expect(screen.getByText("Revoked")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Revoke laptop Claude" }));

        await waitFor(() => expect(authApi.revokeApiKey).toHaveBeenCalled());
        expect(vi.mocked(authApi.revokeApiKey).mock.calls[0][0]).toBe("k1");
    });

    it("shows a new key once, with a ready-to-paste client config", async () => {
        vi.mocked(authApi.listApiKeys).mockResolvedValue([]);
        vi.mocked(authApi.createApiKey).mockResolvedValue({
            id: "k3",
            name: "cursor",
            key_prefix: "mhk_new1",
            key: "mhk_new1-full-secret",
            created_at: "2026-11-12T00:00:00Z",
        });
        renderWithClient(<ApiKeysCard />);
        await screen.findByText("No API keys yet.");

        fireEvent.change(screen.getByLabelText("Key name"), { target: { value: "cursor" } });
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: /Generate key/ }));
        });

        expect(authApi.createApiKey).toHaveBeenCalledWith("cursor", null);
        expect(await screen.findByLabelText("New API key")).toHaveValue("mhk_new1-full-secret");
        expect(screen.getByText(/only time it is shown/)).toBeInTheDocument();
        expect(JSON.parse(mcpClientConfig("mhk_x")).mcpServers["mcp-hub"].headers).toEqual({ "x-api-key": "mhk_x" });
    });

    it("sends the session idle timeout chosen at creation and rejects an out-of-range one", async () => {
        vi.mocked(authApi.listApiKeys).mockResolvedValue([]);
        vi.mocked(authApi.createApiKey).mockResolvedValue({
            id: "k4",
            name: "script",
            key_prefix: "mhk_new2",
            key: "mhk_new2-full-secret",
            created_at: "2026-11-12T00:00:00Z",
            session_idle_minutes: 5,
        });
        renderWithClient(<ApiKeysCard />);
        await screen.findByText("No API keys yet.");

        fireEvent.change(screen.getByLabelText("Key name"), { target: { value: "script" } });
        fireEvent.change(screen.getByLabelText("Session idle timeout (minutes)"), { target: { value: "2000" } });
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: /Generate key/ }));
        });
        expect(await screen.findByText(/Whole minutes from 1 to 1440/)).toBeInTheDocument();
        expect(authApi.createApiKey).not.toHaveBeenCalled();

        fireEvent.change(screen.getByLabelText("Session idle timeout (minutes)"), { target: { value: "5" } });
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: /Generate key/ }));
        });
        expect(authApi.createApiKey).toHaveBeenCalledWith("script", 5);
    });

    it("shows each key's session idle timeout and edits it inline", async () => {
        vi.mocked(authApi.listApiKeys).mockResolvedValue([
            { id: "k1", name: "laptop Claude", key_prefix: "mhk_abcd", created_at: "2026-11-10T00:00:00Z", session_idle_minutes: null },
            { id: "k2", name: "ci", key_prefix: "mhk_efgh", created_at: "2026-11-11T00:00:00Z", session_idle_minutes: 15 },
        ]);
        vi.mocked(authApi.updateApiKey).mockResolvedValue({
            id: "k1",
            name: "laptop Claude",
            key_prefix: "mhk_abcd",
            created_at: "2026-11-10T00:00:00Z",
            session_idle_minutes: 45,
        });
        renderWithClient(<ApiKeysCard />);

        expect(await screen.findByText("30 min (default)")).toBeInTheDocument();
        expect(screen.getByText("15 min")).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: "Edit session idle timeout of laptop Claude" }));
        fireEvent.change(screen.getByLabelText("Session idle timeout of laptop Claude (minutes)"), { target: { value: "45" } });
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Save" }));
        });

        await waitFor(() => expect(authApi.updateApiKey).toHaveBeenCalledWith("k1", 45));
    });
});
