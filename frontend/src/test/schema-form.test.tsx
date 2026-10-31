import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { SchemaForm } from "@/features/playground/components/SchemaForm";

describe("SchemaForm Component", () => {
    const schema = {
        type: "object",
        properties: {
            expression: {
                type: "string",
                description: "Math expression to evaluate",
            },
            precision: {
                type: "integer",
                description: "Decimal places",
                default: 2,
            },
            format: {
                type: "string",
                enum: ["decimal", "fraction", "scientific"],
            },
            verbose: {
                type: "boolean",
                description: "Include verbose steps",
            },
        },
        required: ["expression"],
    };

    it("renders input fields according to schema properties", () => {
        const onChange = vi.fn();
        render(
            <SchemaForm
                schema={schema}
                values={{ expression: "1 + 1", precision: 2, verbose: true }}
                onChange={onChange}
            />
        );

        expect(screen.getByText("expression")).toBeInTheDocument();
        expect(screen.getByText("precision")).toBeInTheDocument();
        expect(screen.getByText("verbose")).toBeInTheDocument();

        const textInput = screen.getByDisplayValue("1 + 1");
        expect(textInput).toBeInTheDocument();

        fireEvent.change(textInput, { target: { value: "2 * 3" } });
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ expression: "2 * 3" }));
    });

    it("renders fallback message when schema has no properties", () => {
        render(<SchemaForm schema={{ type: "object" }} values={{}} onChange={vi.fn()} />);
        expect(
            screen.getByText(/This tool does not define any input parameters/i)
        ).toBeInTheDocument();
    });
});
