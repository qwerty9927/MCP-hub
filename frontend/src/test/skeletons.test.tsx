import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { TableSkeleton } from "@/components/common/TableSkeleton";
import { CardGridSkeleton } from "@/components/common/CardGridSkeleton";
import { ListSkeleton } from "@/components/common/ListSkeleton";
import DashboardLoading from "@/app/(dashboard)/loading";

describe("Skeleton UI Components", () => {
    it("renders TableSkeleton with specified columns and rows", () => {
        const { container } = render(<TableSkeleton columns={["Col 1", "Col 2", "Col 3", "Actions"]} rowCount={4} showPagination={true} />);

        const table = screen.getByRole("table");
        expect(table).toBeInTheDocument();

        // 1 header row + 4 body rows = 5 rows total
        const rows = screen.getAllByRole("row");
        expect(rows).toHaveLength(5);

        // Header cells
        const headers = screen.getAllByRole("columnheader");
        expect(headers).toHaveLength(4);

        // Has animate-pulse skeletons
        const pulseElements = container.querySelectorAll(".animate-pulse");
        expect(pulseElements.length).toBeGreaterThan(10);
    });

    it("renders CardGridSkeleton with specified card count", () => {
        const { container } = render(<CardGridSkeleton count={4} />);

        const pulseElements = container.querySelectorAll(".animate-pulse");
        // Each card has title skeleton, icon skeleton, number skeleton, subtitle skeleton
        expect(pulseElements.length).toBe(16);
    });

    it("renders ListSkeleton with specified item count", () => {
        const { container } = render(<ListSkeleton count={3} />);

        const pulseElements = container.querySelectorAll(".animate-pulse");
        // 3 items * 3 skeletons per item = 9 skeletons
        expect(pulseElements.length).toBe(9);
    });

    it("renders DashboardLoading layout skeleton with table and header", () => {
        render(<DashboardLoading />);

        const table = screen.getByRole("table");
        expect(table).toBeInTheDocument();
    });
});
