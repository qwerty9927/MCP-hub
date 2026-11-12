import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { SessionListTable } from "@/features/sessions/components/SessionListTable";
import { SessionFilterBar } from "@/features/sessions/components/SessionFilterBar";
import { SessionRead } from "@/types";

const mockSessions: SessionRead[] = [
    {
        id: "sess-abc-123-long-id-456",
        title: "Claude Code Agent Session",
        status: "active",
        created_at: "2026-11-09T10:00:00Z",
        last_activity_at: "2026-11-09T10:30:00Z",
        total_tool_calls: 15,
    },
    {
        id: "sess-def-456-other-id-789",
        title: "Gemini CLI Background Runner",
        status: "completed",
        created_at: "2026-11-08T09:00:00Z",
        last_activity_at: "2026-11-08T09:15:00Z",
        total_tool_calls: 3,
    },
    {
        id: "sess-ghi-789-failed-id-012",
        title: null,
        status: "failed",
        created_at: "2026-11-07T08:00:00Z",
        last_activity_at: "2026-11-07T08:05:00Z",
        total_tool_calls: 1,
    },
];

describe("SessionListTable Component", () => {
    it("renders session rows with titles, badges, and tool call counts", () => {
        render(<SessionListTable sessions={mockSessions} />);

        expect(screen.getByText("Claude Code Agent Session")).toBeInTheDocument();
        expect(screen.getByText("Gemini CLI Background Runner")).toBeInTheDocument();
        // Fallback for null title
        expect(screen.getByText("Session sess-ghi")).toBeInTheDocument();

        // Status badges
        expect(screen.getByText("Active")).toBeInTheDocument();
        expect(screen.getByText("Completed")).toBeInTheDocument();
        expect(screen.getByText("Failed")).toBeInTheDocument();

        // Tool call counts
        expect(screen.getByText("15")).toBeInTheDocument();
        expect(screen.getByText("3")).toBeInTheDocument();
        expect(screen.getByText("1")).toBeInTheDocument();

        // View session links
        const viewButtons = screen.getAllByText("View Session");
        expect(viewButtons.length).toBe(3);
    });

    it("copies session ID when copy button is clicked", () => {
        Object.assign(navigator, {
            clipboard: {
                writeText: vi.fn(),
            },
        });

        render(<SessionListTable sessions={mockSessions} />);

        const copyButtons = screen.getAllByTitle("Copy full session ID");
        fireEvent.click(copyButtons[0]);

        expect(navigator.clipboard.writeText).toHaveBeenCalledWith("sess-abc-123-long-id-456");
    });
});

describe("SessionFilterBar Component", () => {
    it("updates filters when user types into search input", () => {
        const handleChange = vi.fn();
        render(<SessionFilterBar filters={{ page: 1, page_size: 20 }} onChange={handleChange} />);

        const searchInput = screen.getByPlaceholderText("Search session ID or title...");
        fireEvent.change(searchInput, { target: { value: "Claude" } });

        expect(handleChange).toHaveBeenCalledWith(
            expect.objectContaining({
                search: "Claude",
                page: 1,
            })
        );
    });

    it("shows Reset button when filters are active and clears filters on click", () => {
        const handleChange = vi.fn();
        render(<SessionFilterBar filters={{ page: 1, page_size: 20, search: "Claude", status: "active" }} onChange={handleChange} />);

        const resetButton = screen.getByRole("button", { name: /reset/i });
        expect(resetButton).toBeInTheDocument();

        fireEvent.click(resetButton);
        expect(handleChange).toHaveBeenCalledWith(
            expect.objectContaining({
                page: 1,
                page_size: 20,
                search: undefined,
                status: undefined,
            })
        );
    });
});
