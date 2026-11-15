import { describe, it, expect, vi } from "vitest";
import { render, act } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthGuard } from "@/components/layout/AuthGuard";
import { AUTH_TOKEN_KEY } from "@/lib/auth-token";

// During hydration React renders with the store's *server* snapshot, which for sessionStorage is always null.
// Pin the snapshot to null to reproduce that render.
vi.mock("react", async (importOriginal) => {
    const actual = await importOriginal<typeof import("react")>();
    return { ...actual, useSyncExternalStore: () => null };
});

const replace = vi.fn();
vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace, push: vi.fn() }),
    usePathname: () => "/settings",
}));

vi.mock("@/lib/api", () => ({ authApi: { me: vi.fn() } }));

describe("AuthGuard on a hard page load", () => {
    it("does not send a signed-in user to the login page", async () => {
        sessionStorage.setItem(AUTH_TOKEN_KEY, "jwt-123");
        const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

        await act(async () => {
            render(
                <QueryClientProvider client={client}>
                    <AuthGuard>
                        <p>dashboard</p>
                    </AuthGuard>
                </QueryClientProvider>
            );
        });

        expect(replace).not.toHaveBeenCalled();
    });
});
