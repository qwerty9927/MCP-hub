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
                minimum: 0,
                maximum: 10,
            },
            format: {
                type: "string",
                enum: ["decimal", "fraction", "scientific"],
            },
            verbose: {
                type: "boolean",
                description: "Include verbose steps",
                default: false,
            },
            tags: {
                type: "array",
                description: "Tags list",
            },
            metadata: {
                type: "object",
                description: "Metadata dict",
            },
        },
        required: ["expression"],
    };

    it("renders input fields according to schema properties", () => {
        const onChange = vi.fn();
        render(<SchemaForm schema={schema} values={{ expression: "1 + 1", precision: 2, verbose: true }} onChange={onChange} />);

        expect(screen.getByText("expression")).toBeInTheDocument();
        expect(screen.getByText("precision")).toBeInTheDocument();
        expect(screen.getByText("verbose")).toBeInTheDocument();
        expect(screen.getByText("tags")).toBeInTheDocument();
        expect(screen.getByText("metadata")).toBeInTheDocument();

        const textInput = screen.getByDisplayValue("1 + 1");
        expect(textInput).toBeInTheDocument();

        fireEvent.change(textInput, { target: { value: "2 * 3" } });
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ expression: "2 * 3" }));
    });

    it("renders fallback message when schema has no properties", () => {
        render(<SchemaForm schema={{ type: "object" }} values={{}} onChange={vi.fn()} />);
        expect(screen.getByText(/This tool does not define any input parameters/i)).toBeInTheDocument();
    });

    it("handles number/integer inputs with conversion and clearing", () => {
        const onChange = vi.fn();
        render(<SchemaForm schema={schema} values={{ precision: 2 }} onChange={onChange} />);

        const numberInput = screen.getByDisplayValue("2");
        expect(numberInput).toBeInTheDocument();

        fireEvent.change(numberInput, { target: { value: "5" } });
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ precision: 5 }));

        fireEvent.change(numberInput, { target: { value: "" } });
        expect(onChange).toHaveBeenCalledWith({});
    });

    it("handles boolean switch toggling", () => {
        const onChange = vi.fn();
        render(<SchemaForm schema={schema} values={{ verbose: false }} onChange={onChange} />);

        const switchEl = screen.getByRole("switch");
        expect(switchEl).toBeInTheDocument();
        expect(switchEl).not.toBeChecked();

        fireEvent.click(switchEl);
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ verbose: true }));
    });

    it("handles array and object inputs with JSON parsing", () => {
        const onChange = vi.fn();
        render(<SchemaForm schema={schema} values={{}} onChange={onChange} />);

        const arrayInput = screen.getByPlaceholderText('["item1", "item2"]');
        fireEvent.change(arrayInput, { target: { value: '["tag1", "tag2"]' } });
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ tags: ["tag1", "tag2"] }));

        const objectInput = screen.getByPlaceholderText(/\{\s*"key": "value"\s*\}/);
        fireEvent.change(objectInput, { target: { value: '{"author": "alice"}' } });
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ metadata: { author: "alice" } }));
    });

    it("displays validation error message when field has error", () => {
        render(<SchemaForm schema={schema} values={{}} onChange={vi.fn()} errors={{ expression: "This parameter is required" }} />);

        expect(screen.getByText("This parameter is required")).toBeInTheDocument();
    });

    it("resets form values to schema defaults when reset button is clicked", () => {
        const onChange = vi.fn();
        render(<SchemaForm schema={schema} values={{ expression: "3 + 3", precision: 8 }} onChange={onChange} />);

        const resetBtn = screen.getByRole("button", { name: /Reset to Defaults/i });
        expect(resetBtn).toBeInTheDocument();

        fireEvent.click(resetBtn);
        expect(onChange).toHaveBeenCalledWith({ precision: 2, verbose: false });
    });
});
