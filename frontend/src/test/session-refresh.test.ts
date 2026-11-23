import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AxiosError, AxiosHeaders, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import { apiClient, axiosInstance, refreshSession, REFRESH_LOCK_NAME } from "@/lib/api-client";
import { AUTH_TOKEN_KEY, getAuthToken } from "@/lib/auth-token";

type Handler = (config: InternalAxiosRequestConfig) => { status: number; data?: unknown };

const originalAdapter = axiosInstance.defaults.adapter;
let calls: InternalAxiosRequestConfig[] = [];

/** Route every request through `handler` instead of the network, the way a real adapter settles responses. */
function serve(handler: Handler) {
    axiosInstance.defaults.adapter = async (config) => {
        calls.push(config);
        // Let concurrent requests all be in flight before any of them settles.
        await new Promise((resolve) => setTimeout(resolve, 0));
        const { status, data = {} } = handler(config);
        const response: AxiosResponse = { status, statusText: String(status), headers: {}, config, data };
        if (status >= 400) throw new AxiosError(`HTTP ${status}`, "ERR_BAD_REQUEST", config, null, response);
        return response;
    };
}

function authOf(config: InternalAxiosRequestConfig): string | undefined {
    return (AxiosHeaders.from(config.headers).get("Authorization") as string | null) ?? undefined;
}

const refreshCalls = () => calls.filter((c) => c.url === "/auth/refresh");

/** A protected endpoint that only accepts `valid`, and a refresh endpoint handing out `next` (or failing). */
function backend(valid: string, next: string | null): Handler {
    return (config) => {
        if (config.url === "/auth/refresh") {
            return next ? { status: 200, data: { access_token: next, token_type: "bearer", expires_in: 900 } } : { status: 401 };
        }
        return authOf(config) === `Bearer ${valid}` ? { status: 200, data: { url: config.url } } : { status: 401 };
    };
}

let assign: ReturnType<typeof vi.fn>;

beforeEach(() => {
    calls = [];
    sessionStorage.clear();
    assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, pathname: "/servers", search: "", assign });
});

afterEach(() => {
    axiosInstance.defaults.adapter = originalAdapter;
    vi.unstubAllGlobals();
});

describe("refresh on 401", () => {
    it("refreshes the access token and retries the request once", async () => {
        sessionStorage.setItem(AUTH_TOKEN_KEY, "expired");
        serve(backend("fresh", "fresh"));

        const data = await apiClient<{ url: string }>({ url: "/servers", method: "GET" });

        expect(data).toEqual({ url: "/servers" });
        expect(getAuthToken()).toBe("fresh");
        expect(calls.map((c) => c.url)).toEqual(["/servers", "/auth/refresh", "/servers"]);
        expect(authOf(calls[2])).toBe("Bearer fresh");
        const [refresh] = refreshCalls();
        expect(refresh.withCredentials).toBe(true);
        expect(AxiosHeaders.from(refresh.headers).get("X-MCP-Hub-Client")).toBe("console");
        expect(authOf(refresh)).toBeUndefined(); // the expired token is not sent to /auth/refresh
        expect(assign).not.toHaveBeenCalled();
    });

    it("shares one refresh between requests that fail together", async () => {
        sessionStorage.setItem(AUTH_TOKEN_KEY, "expired");
        serve(backend("fresh", "fresh"));

        const results = await Promise.all([
            apiClient({ url: "/servers", method: "GET" }),
            apiClient({ url: "/tools", method: "GET" }),
            apiClient({ url: "/sessions", method: "GET" }),
        ]);

        expect(results).toEqual([{ url: "/servers" }, { url: "/tools" }, { url: "/sessions" }]);
        expect(refreshCalls()).toHaveLength(1);
    });

    it("reuses a token another request already refreshed instead of rotating again", async () => {
        sessionStorage.setItem(AUTH_TOKEN_KEY, "expired");
        serve(backend("fresh", "fresh"));
        await apiClient({ url: "/servers", method: "GET" });
        calls = [];

        // A request that left with the old token comes back 401 after the refresh finished.
        await apiClient({ url: "/tools", method: "GET", headers: { Authorization: "Bearer expired" } });

        expect(refreshCalls()).toHaveLength(0);
        expect(authOf(calls[1])).toBe("Bearer fresh");
    });

    it("signs out when the refresh token is rejected", async () => {
        sessionStorage.setItem(AUTH_TOKEN_KEY, "expired");
        serve(backend("fresh", null));

        await expect(apiClient({ url: "/servers", method: "GET" })).rejects.toMatchObject({ status: 401 });

        expect(getAuthToken()).toBeNull();
        expect(assign).toHaveBeenCalledWith("/login?next=%2Fservers");
        expect(calls.map((c) => c.url)).toEqual(["/servers", "/auth/refresh"]);
    });

    it("signs out instead of looping when the retried request is still unauthorized", async () => {
        sessionStorage.setItem(AUTH_TOKEN_KEY, "expired");
        serve(backend("never-valid", "fresh"));

        await expect(apiClient({ url: "/servers", method: "GET" })).rejects.toMatchObject({ status: 401 });

        expect(refreshCalls()).toHaveLength(1);
        expect(calls).toHaveLength(3);
        expect(getAuthToken()).toBeNull();
        expect(assign).toHaveBeenCalled();
    });

    it("does not refresh on a failed login", async () => {
        serve(() => ({ status: 401 }));

        await expect(apiClient({ url: "/auth/login", method: "POST", data: {} })).rejects.toMatchObject({ status: 401 });

        expect(refreshCalls()).toHaveLength(0);
        expect(assign).not.toHaveBeenCalled();
    });

    it("leaves other errors alone", async () => {
        sessionStorage.setItem(AUTH_TOKEN_KEY, "valid");
        serve(() => ({ status: 403 }));

        await expect(apiClient({ url: "/servers", method: "GET" })).rejects.toMatchObject({ status: 403 });

        expect(refreshCalls()).toHaveLength(0);
        expect(getAuthToken()).toBe("valid");
    });
});

describe("refreshSession", () => {
    it("holds a Web Lock so tabs sharing the cookie refresh one at a time", async () => {
        const request = vi.fn((_name: string, task: () => Promise<unknown>) => task());
        vi.stubGlobal("navigator", { ...navigator, locks: { request } });
        serve(backend("fresh", "fresh"));

        expect(await refreshSession()).toBe("fresh");

        expect(request).toHaveBeenCalledTimes(1);
        expect(request.mock.calls[0][0]).toBe(REFRESH_LOCK_NAME);
    });

    it("returns null and stores nothing when the sign-in is over", async () => {
        serve(backend("fresh", null));

        expect(await refreshSession()).toBeNull();

        expect(getAuthToken()).toBeNull();
        expect(assign).not.toHaveBeenCalled(); // the caller decides where to go
    });
});
