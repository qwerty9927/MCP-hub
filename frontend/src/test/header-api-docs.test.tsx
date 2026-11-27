import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";

// SHOW_API_DOCS is fixed at build time in the app; the getter lets each test pick it.
const docs = vi.hoisted(() => ({ show: true }));

vi.mock("@/lib/config", () => ({
    API_BASE_URL: "http://localhost:8000/api/v1",
    API_DOCS_URL: "http://localhost:8000/docs",
    get SHOW_API_DOCS() {
        return docs.show;
    },
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("@/features/auth/hooks/use-auth", () => ({
    useMe: () => ({ data: { email: "owner@test.local" } }),
    useLogout: () => vi.fn(),
}));

vi.mock("@/components/common/ThemeToggle", () => ({
    ThemeToggle: () => null,
}));

import { Header } from "@/components/layout/Header";

async function openAccountMenu() {
    await userEvent.click(screen.getByRole("button", { name: /owner@test\.local/ }));
}

describe("Header API docs links", () => {
    beforeEach(() => {
        docs.show = true;
    });

    it("links to the backend's Swagger docs outside production builds", async () => {
        render(<Header />);

        expect(screen.getByRole("link", { name: /Swagger Docs/ })).toHaveAttribute("href", "http://localhost:8000/docs");
        await openAccountMenu();
        expect(await screen.findByRole("menuitem", { name: /Interactive OpenAPI/ })).toHaveAttribute("href", "http://localhost:8000/docs");
    });

    it("hides both links in production builds, where the backend serves no docs", async () => {
        docs.show = false;
        render(<Header />);

        expect(screen.queryByRole("link", { name: /Swagger Docs/ })).not.toBeInTheDocument();
        await openAccountMenu();
        expect(await screen.findByText(/Backend: http:\/\/localhost:8000\/api\/v1/)).toBeInTheDocument();
        expect(screen.queryByRole("menuitem", { name: /Interactive OpenAPI/ })).not.toBeInTheDocument();
        expect(screen.getByRole("menuitem", { name: /Sign out/ })).toBeInTheDocument();
    });
});
