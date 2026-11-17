import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { HealthBadge } from "@/components/common/HealthBadge";

describe("HealthBadge Component", () => {
    it("renders Healthy status correctly", () => {
        render(<HealthBadge status="HEALTHY" />);
        expect(screen.getByText("Healthy")).toBeInTheDocument();
    });

    it("renders Available status correctly", () => {
        render(<HealthBadge status="AVAILABLE" />);
        expect(screen.getByText("Available")).toBeInTheDocument();
    });

    it("renders Unhealthy status correctly", () => {
        render(<HealthBadge status="UNHEALTHY" />);
        expect(screen.getByText("Unhealthy")).toBeInTheDocument();
    });

    it("renders Disconnected status correctly", () => {
        render(<HealthBadge status="DISCONNECTED" />);
        expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });

    it("renders Needs Auth as a warning asking to sign in again", () => {
        render(<HealthBadge status="NEEDS_AUTH" />);
        expect(screen.getByText("Sign in again")).toHaveClass("text-amber-700");
    });

    it("renders Unknown status gracefully", () => {
        render(<HealthBadge status="UNKNOWN" />);
        expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
    });
});
