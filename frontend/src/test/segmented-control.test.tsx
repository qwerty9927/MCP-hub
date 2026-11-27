import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { SegmentedControl } from "@/components/common/SegmentedControl";

const OPTIONS = [
    { value: "1h", label: "Last hour", disabled: true },
    { value: "24h", label: "Last 24 hours" },
    { value: "7d", label: "Last 7 days" },
];

describe("SegmentedControl", () => {
    it("is a named group of toggle buttons with the current one pressed", () => {
        render(<SegmentedControl label="Time range" value="24h" onValueChange={vi.fn()} options={OPTIONS} />);

        const group = screen.getByRole("group", { name: "Time range" });
        expect(group).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Last 24 hours" })).toHaveAttribute("aria-pressed", "true");
        expect(screen.getByRole("button", { name: "Last 7 days" })).toHaveAttribute("aria-pressed", "false");
    });

    it("reports the picked value and ignores disabled options", async () => {
        const onValueChange = vi.fn();
        render(<SegmentedControl label="Time range" value="24h" onValueChange={onValueChange} options={OPTIONS} />);

        await userEvent.click(screen.getByRole("button", { name: "Last 7 days" }));
        expect(onValueChange).toHaveBeenCalledWith("7d");

        expect(screen.getByRole("button", { name: "Last hour" })).toBeDisabled();
        await userEvent.click(screen.getByRole("button", { name: "Last hour" }));
        expect(onValueChange).toHaveBeenCalledTimes(1);
    });
});
