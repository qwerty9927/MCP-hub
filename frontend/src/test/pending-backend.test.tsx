import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { PendingBadge, PendingFeature } from "@/components/common/PendingBackend";
import { BACKEND_PENDING } from "@/lib/backend-pending";

describe("Backend pending UI", () => {
    it("badge names the feature and shows what the backend must provide", async () => {
        render(<PendingBadge id="server-rate-limit" />);

        const badge = screen.getByRole("button", { name: "Backend pending: Calls against a rate limit" });
        expect(badge).toHaveTextContent("Backend pending");
        await userEvent.hover(badge);
        expect((await screen.findAllByText(BACKEND_PENDING["server-rate-limit"].needs)).length).toBeGreaterThan(0);
    });

    it("feature wrapper keeps the control visible but inert, with the badge beside it", () => {
        render(
            <PendingFeature id="profile-delete">
                <button type="button">Delete Profile</button>
            </PendingFeature>
        );

        const wrapper = screen.getByText("Delete Profile").parentElement as HTMLElement;
        expect(wrapper).toHaveAttribute("aria-disabled", "true");
        expect(wrapper).toHaveAttribute("inert");
        expect(screen.getByRole("button", { name: "Backend pending: Delete profile" })).toBeInTheDocument();
    });

    it("every pending item has a row in docs/backend-pending.md", () => {
        const doc = readFileSync(resolve(__dirname, "../../docs/backend-pending.md"), "utf8");
        for (const id of Object.keys(BACKEND_PENDING)) {
            expect(doc, `docs/backend-pending.md is missing ${id}`).toContain(`\`${id}\``);
        }
    });
});
