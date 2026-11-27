import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// SHOW_BACKEND_DETAILS is fixed at build time in the app (false in production builds); the getter lets each test pick it.
const backend = vi.hoisted(() => ({ show: true }));

vi.mock("@/lib/config", () => ({
    API_BASE_URL: "http://localhost:8000/api/v1",
    API_DOCS_URL: "http://localhost:8000/docs",
    get SHOW_BACKEND_DETAILS() {
        return backend.show;
    },
}));

const probes = vi.hoisted(() => ({
    health: vi.fn(async () => ({ status: "ok", version: "0.1.0" })),
    readiness: vi.fn(async () => ({ status: "ready" })),
}));

vi.mock("@/lib/api", () => ({ systemApi: probes }));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace: vi.fn() }),
    usePathname: () => "/settings",
}));

vi.mock("@/features/auth/hooks/use-auth", () => ({
    useMe: () => ({ data: { email: "owner@test.local" } }),
    useLogout: () => vi.fn(),
}));

vi.mock("@/components/common/ThemeToggle", () => ({ ThemeToggle: () => null }));
vi.mock("@/features/auth/components/ApiKeysCard", () => ({ ApiKeysCard: () => null }));
vi.mock("next-themes", () => ({ useTheme: () => ({ theme: "light", setTheme: vi.fn() }) }));

import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import SettingsPage from "@/app/(dashboard)/settings/page";

function renderWithQueries(ui: React.ReactElement) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

async function openAccountMenu() {
    await userEvent.click(screen.getByRole("button", { name: /owner@test\.local/ }));
}

beforeEach(() => {
    backend.show = true;
    probes.health.mockClear();
    probes.readiness.mockClear();
});

describe("backend details outside production builds", () => {
    it("header links to the Swagger docs and names the backend", async () => {
        render(<Header />);

        expect(screen.getByRole("link", { name: /Swagger Docs/ })).toHaveAttribute("href", "http://localhost:8000/docs");
        await openAccountMenu();
        expect(await screen.findByRole("menuitem", { name: /Interactive OpenAPI/ })).toHaveAttribute("href", "http://localhost:8000/docs");
        expect(screen.getByText("Backend: http://localhost:8000/api/v1")).toBeInTheDocument();
    });

    it("sidebar shows the backend status and version", async () => {
        renderWithQueries(<Sidebar />);

        expect(screen.getByText("Backend API")).toBeInTheDocument();
        expect(await screen.findByText("v0.1.0")).toBeInTheDocument();
        expect(probes.health).toHaveBeenCalled();
    });

    it("settings shows the backend connection card with live probes", async () => {
        renderWithQueries(<SettingsPage />);

        expect(screen.getByText("Backend Connection")).toBeInTheDocument();
        expect(screen.getByDisplayValue("http://localhost:8000/api/v1")).toBeInTheDocument();
        expect(await screen.findByText("OK (v0.1.0)")).toBeInTheDocument();
        expect(probes.readiness).toHaveBeenCalled();
    });
});

describe("backend details in production builds", () => {
    beforeEach(() => {
        backend.show = false;
    });

    it("header hides the docs links and the backend URL", async () => {
        render(<Header />);

        expect(screen.queryByRole("link", { name: /Swagger Docs/ })).not.toBeInTheDocument();
        await openAccountMenu();
        expect(await screen.findByRole("menuitem", { name: /Sign out/ })).toBeInTheDocument();
        expect(screen.queryByRole("menuitem", { name: /Interactive OpenAPI/ })).not.toBeInTheDocument();
        expect(screen.queryByText(/Backend: /)).not.toBeInTheDocument();
    });

    it("sidebar hides the backend status footer and does not poll /health", async () => {
        renderWithQueries(<Sidebar />);

        expect(screen.getByText("Overview")).toBeInTheDocument();
        expect(screen.queryByText("Backend API")).not.toBeInTheDocument();
        await waitFor(() => expect(probes.health).not.toHaveBeenCalled());
    });

    it("settings hides the backend connection card and sends no probes", async () => {
        renderWithQueries(<SettingsPage />);

        expect(screen.getByText("Appearance")).toBeInTheDocument();
        expect(screen.queryByText("Backend Connection")).not.toBeInTheDocument();
        expect(screen.queryByDisplayValue("http://localhost:8000/api/v1")).not.toBeInTheDocument();
        await waitFor(() => {
            expect(probes.health).not.toHaveBeenCalled();
            expect(probes.readiness).not.toHaveBeenCalled();
        });
    });
});
