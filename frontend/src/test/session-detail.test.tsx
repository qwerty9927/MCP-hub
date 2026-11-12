import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { SessionOverview } from "@/features/sessions/components/SessionOverview";
import { ToolExecutionTimeline } from "@/features/sessions/components/ToolExecutionTimeline";
import { ServerToolGroup } from "@/features/sessions/components/ServerToolGroup";
import { ToolCallDetailDrawer } from "@/features/sessions/components/ToolCallDetailDrawer";
import { SessionDetailRead, ToolCallRead } from "@/types";

const mockSessionDetail: SessionDetailRead = {
    id: "session-xyz-987",
    title: "Test Agent Session",
    status: "active",
    created_at: "2026-11-09T10:00:00Z",
    last_activity_at: "2026-11-09T10:45:00Z",
    total_tool_calls: 8,
    successful_tool_calls: 2,
    failed_tool_calls: 1,
    rejected_tool_calls: 5,
    metadata: {
        client: "claude-desktop",
        env: "staging",
    },
};

const mockToolCalls: ToolCallRead[] = [
    {
        id: "call-1",
        session_id: "session-xyz-987",
        server_name: "math-server",
        tool_name: "calculate",
        status: "completed",
        started_at: "2026-11-09T10:05:00Z",
        completed_at: "2026-11-09T10:05:01Z",
        duration_ms: 1050,
        error_summary: null,
        arguments: { expression: "2 + 2" },
        response: { result: 4 },
    },
    {
        id: "call-2",
        session_id: "session-xyz-987",
        server_name: "data-server",
        tool_name: "query_database",
        status: "completed",
        started_at: "2026-11-09T10:10:00Z",
        completed_at: "2026-11-09T10:10:02Z",
        duration_ms: 2100,
        error_summary: null,
        arguments: { table: "users" },
        response: { rows: 42 },
    },
    {
        id: "call-3",
        session_id: "session-xyz-987",
        server_name: "math-server",
        tool_name: "divide",
        status: "failed",
        started_at: "2026-11-09T10:15:00Z",
        completed_at: "2026-11-09T10:15:01Z",
        duration_ms: 50,
        error_summary: "ZeroDivisionError: division by zero",
        arguments: { a: 10, b: 0 },
        response: null,
    },
];

describe("SessionOverview Component", () => {
    it("renders session title, aggregated metrics, and metadata", () => {
        render(<SessionOverview session={mockSessionDetail} />);

        expect(screen.getByText("Test Agent Session")).toBeInTheDocument();
        expect(screen.getAllByText("Active").length).toBeGreaterThanOrEqual(1);

        // Metric numbers
        expect(screen.getByText("8")).toBeInTheDocument(); // total calls
        expect(screen.getByText("2")).toBeInTheDocument(); // successful
        expect(screen.getByText("1")).toBeInTheDocument(); // failed
        expect(screen.getByText("Rejected")).toBeInTheDocument();
        expect(screen.getByText("5")).toBeInTheDocument(); // rejected, its own bucket

        // Metadata badges
        expect(screen.getByText(/client:\s*claude-desktop/i)).toBeInTheDocument();
        expect(screen.getByText(/env:\s*staging/i)).toBeInTheDocument();
    });
});

describe("ToolExecutionTimeline (Mode A: Chronological)", () => {
    it("renders tool calls in chronological order and handles click selection", () => {
        const handleSelect = vi.fn();
        render(<ToolExecutionTimeline toolCalls={mockToolCalls} selectedCallId="call-1" onSelectCall={handleSelect} />);

        expect(screen.getByText("calculate")).toBeInTheDocument();
        expect(screen.getByText("query_database")).toBeInTheDocument();
        expect(screen.getByText("divide")).toBeInTheDocument();

        // Clicking tool item selects it
        fireEvent.click(screen.getByText("divide"));
        expect(handleSelect).toHaveBeenCalledWith(mockToolCalls[2]);
    });
});

describe("ServerToolGroup (Mode B: Frontend Grouping)", () => {
    it("groups tool calls by server_name and shows counts", () => {
        const handleSelect = vi.fn();
        render(<ServerToolGroup toolCalls={mockToolCalls} selectedCallId={null} onSelectCall={handleSelect} />);

        // Group headers
        expect(screen.getByText("math-server")).toBeInTheDocument();
        expect(screen.getByText("data-server")).toBeInTheDocument();

        // Group counts
        expect(screen.getByText("2 calls")).toBeInTheDocument(); // math-server has 2
        expect(screen.getByText("1 call")).toBeInTheDocument(); // data-server has 1

        // All tools are visible initially
        expect(screen.getByText("calculate")).toBeInTheDocument();
        expect(screen.getByText("divide")).toBeInTheDocument();
        expect(screen.getByText("query_database")).toBeInTheDocument();

        // Clicking a tool call within group triggers selection
        fireEvent.click(screen.getByText("query_database"));
        expect(handleSelect).toHaveBeenCalledWith(mockToolCalls[1]);
    });

    it("collapses and expands server groups on toggle", () => {
        render(<ServerToolGroup toolCalls={mockToolCalls} selectedCallId={null} onSelectCall={vi.fn()} />);

        // Click math-server header to collapse
        const mathHeader = screen.getByText("math-server");
        fireEvent.click(mathHeader);

        // calculate and divide should now be hidden
        expect(screen.queryByText("calculate")).not.toBeInTheDocument();
        expect(screen.queryByText("divide")).not.toBeInTheDocument();

        // data-server is still visible
        expect(screen.getByText("query_database")).toBeInTheDocument();

        // Click again to expand
        fireEvent.click(mathHeader);
        expect(screen.getByText("calculate")).toBeInTheDocument();
    });
});

describe("ToolCallDetailDrawer Component", () => {
    it("renders drawer details, JSON arguments, response, and error banner", () => {
        const handleClose = vi.fn();
        render(
            <ToolCallDetailDrawer
                toolCall={mockToolCalls[2]} // failed call
                open={true}
                onOpenChange={handleClose}
            />
        );

        expect(screen.getByText("divide")).toBeInTheDocument();
        expect(screen.getByText("math-server")).toBeInTheDocument();
        expect(screen.getByText("ZeroDivisionError: division by zero")).toBeInTheDocument();
        expect(screen.getByText(/"a": 10/)).toBeInTheDocument();
        expect(screen.getByText("No response payload recorded")).toBeInTheDocument();
    });

    it("renders response payload for successful call", () => {
        render(
            <ToolCallDetailDrawer
                toolCall={mockToolCalls[0]} // successful call with result: 4
                open={true}
                onOpenChange={vi.fn()}
            />
        );

        expect(screen.getByText("calculate")).toBeInTheDocument();
        expect(screen.getByText(/"expression": "2 \+ 2"/)).toBeInTheDocument();
        expect(screen.getByText(/"result": 4/)).toBeInTheDocument();
    });
});

describe("Rejected tool calls (ADR-0002)", () => {
    const rejectedCall: ToolCallRead = {
        id: "call-4",
        session_id: "session-xyz-987",
        server_name: "math-server",
        tool_name: "add",
        status: "rejected",
        started_at: "2026-11-09T10:20:00Z",
        completed_at: "2026-11-09T10:20:00Z",
        duration_ms: 0,
        error_summary: "'b' is a required property",
        arguments: { a: 1 },
        response: null,
    };

    it("shows a Rejected badge in the timeline", () => {
        render(<ToolExecutionTimeline toolCalls={[rejectedCall]} selectedCallId={null} onSelectCall={vi.fn()} />);

        expect(screen.getByText("Rejected")).toBeInTheDocument();
        expect(screen.queryByText("Failed")).not.toBeInTheDocument();
    });

    it("counts rejected calls separately from failed ones in a server group", () => {
        render(<ServerToolGroup toolCalls={[...mockToolCalls, rejectedCall]} selectedCallId={null} onSelectCall={vi.fn()} />);

        expect(screen.getByText("1 failed")).toBeInTheDocument();
        expect(screen.getByText("1 rejected")).toBeInTheDocument();
    });

    it("shows the rejection reason in the drawer", () => {
        render(<ToolCallDetailDrawer toolCall={rejectedCall} open={true} onOpenChange={vi.fn()} />);

        expect(screen.getByText("Rejected")).toBeInTheDocument();
        expect(screen.getByText("Execution Rejected")).toBeInTheDocument();
        expect(screen.getByText("'b' is a required property")).toBeInTheDocument();
    });
});
