import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Mock next/navigation
vi.mock("next/navigation", () => ({
    usePathname: () => "/servers",
}));

describe("Sidebar Navigation Component", () => {
    const queryClient = new QueryClient();

    it("renders branding and all main navigation items", () => {
        render(
            <QueryClientProvider client={queryClient}>
                <Sidebar />
            </QueryClientProvider>
        );

        expect(screen.getByText("MCP Hub")).toBeInTheDocument();
        expect(screen.getByText("Admin Console")).toBeInTheDocument();

        expect(screen.getByText("Overview")).toBeInTheDocument();
        expect(screen.getByText("MCP Servers")).toBeInTheDocument();
        expect(screen.getByText("Tool Catalog")).toBeInTheDocument();
        expect(screen.getByText("Tool Playground")).toBeInTheDocument();
        expect(screen.getByText("Execution History")).toBeInTheDocument();
        expect(screen.getByText("Settings")).toBeInTheDocument();
    });
});
