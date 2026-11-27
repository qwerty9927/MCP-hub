import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import React from "react";

const nav = vi.hoisted(() => ({ pathname: "/settings/members" }));

vi.mock("next/navigation", () => ({
    usePathname: () => nav.pathname,
    notFound: () => {
        throw new Error("NEXT_NOT_FOUND");
    },
}));

import { SettingsNav } from "@/features/settings/components/SettingsNav";
import PendingSectionPage from "@/app/(dashboard)/settings/[section]/page";
import { PENDING_SECTIONS, SETTINGS_GROUPS } from "@/features/settings/sections";

describe("Settings sections", () => {
    it("lists User and Hub sections and marks the current one", () => {
        render(<SettingsNav />);

        const settingsNav = screen.getByRole("navigation", { name: "Settings" });
        expect(within(settingsNav).getByText("User settings")).toBeInTheDocument();
        expect(within(settingsNav).getByText("Hub settings")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Members/ })).toHaveAttribute("aria-current", "page");
        expect(screen.getByRole("link", { name: "API Keys" })).toHaveAttribute("href", "/settings/api-keys");
        // Placeholder sections say so to screen readers.
        expect(screen.getByRole("link", { name: /Audit Logs \(backend pending\)/ })).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "System" })).not.toHaveTextContent("backend pending");
    });

    it("renders a pending section with its badge", async () => {
        render(await PendingSectionPage({ params: Promise.resolve({ section: "members" }) }));

        expect(screen.getByRole("heading", { name: "Members" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Backend pending: Members" })).toBeInTheDocument();
        expect(screen.getByText("Members is on the way")).toBeInTheDocument();
    });

    it("404s for a slug that is not a pending section", async () => {
        await expect(PendingSectionPage({ params: Promise.resolve({ section: "nope" }) })).rejects.toThrow("NEXT_NOT_FOUND");
    });

    it("has a placeholder for every pending section in the nav", () => {
        const pendingHrefs = SETTINGS_GROUPS.flatMap((group) => group.sections)
            .filter((section) => section.pending)
            .map((section) => section.href.split("/").pop());
        expect(Object.keys(PENDING_SECTIONS).sort()).toEqual(pendingHrefs.sort());
    });
});
