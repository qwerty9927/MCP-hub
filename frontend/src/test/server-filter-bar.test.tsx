import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { ServerFilterBar } from "@/features/servers/components/ServerFilterBar";
import { SERVER_SORT_OPTIONS } from "@/features/servers/sort-options";
import { ServerFilterParams } from "@/types";

// The fields GET /servers accepts for sort_by; anything else is a 422 (backend ServerSortField).
const BACKEND_SORT_FIELDS = ["created_at", "name", "updated_at"];

const FILTERS: ServerFilterParams = { page: 3, page_size: 20, sort_by: "created_at", sort_order: "desc" };

describe("ServerFilterBar sorting", () => {
    it("offers only sort fields the backend accepts", () => {
        for (const option of SERVER_SORT_OPTIONS) {
            expect(BACKEND_SORT_FIELDS).toContain(option.sort_by);
            expect(["asc", "desc"]).toContain(option.sort_order);
        }
    });

    it.each([
        ["Oldest First", "created_at", "asc"],
        ["Newest First", "created_at", "desc"],
        ["Name (Z-A)", "name", "desc"],
        ["Recently Updated", "updated_at", "desc"],
    ])("sends a whole field name when choosing %s", async (label, sortBy, sortOrder) => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(<ServerFilterBar filters={{ ...FILTERS, sort_by: "name", sort_order: "asc" }} onChange={onChange} />);

        await user.click(screen.getByRole("combobox", { name: "Sort servers" }));
        await user.click(await screen.findByRole("option", { name: label }));

        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ sort_by: sortBy, sort_order: sortOrder, page: 1 }));
    });

    it("shows the current sort", () => {
        render(<ServerFilterBar filters={{ ...FILTERS, sort_by: "updated_at", sort_order: "desc" }} onChange={vi.fn()} />);

        expect(screen.getByRole("combobox", { name: "Sort servers" })).toHaveTextContent("Recently Updated");
    });
});
