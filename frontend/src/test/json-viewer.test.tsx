import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { ContentBlock, JsonTabs, JsonViewer, parseJsonText } from "@/components/common/JsonViewer";

describe("parseJsonText", () => {
    it.each([
        ['{"a": 1}', { a: 1 }],
        ["[1, 2]", [1, 2]],
    ])("parses JSON objects and arrays: %s", (text, expected) => {
        expect(parseJsonText(text)).toEqual(expected);
    });

    it.each(["hello", "20", "true", "null", '"quoted"', "{broken"])("keeps other text as text: %s", (text) => {
        expect(parseJsonText(text)).toBeNull();
    });
});

describe("ContentBlock", () => {
    it("renders a text block holding JSON as a tree, not as the raw string", () => {
        const text = JSON.stringify({ data: [{ timestamp: "1795140650886079044", line: "INFORMATION" }] });
        render(<ContentBlock item={{ type: "text", text }} />);

        expect(screen.getByText("data")).toBeInTheDocument();
        expect(screen.queryByText(text)).not.toBeInTheDocument();
    });

    it("renders plain text as text", () => {
        render(<ContentBlock item={{ type: "text", text: "Result: 30" }} />);

        expect(screen.getByText("Result: 30")).toBeInTheDocument();
    });

    it("renders a block without text (e.g. an image) as a tree", () => {
        render(<ContentBlock item={{ type: "image", data: "aGk=" }} />);

        expect(screen.getByText("type")).toBeInTheDocument();
        expect(screen.getByText("image")).toBeInTheDocument();
    });
});

describe("JsonViewer", () => {
    it("falls back to text for a value that is not an object or array", () => {
        render(<JsonViewer value={42} />);

        expect(screen.getByText("42").tagName).toBe("PRE");
    });
});

describe("JsonTabs", () => {
    it("shows the formatted view first and the pretty-printed JSON on Raw JSON", () => {
        const value = { expression: "2 + 2" };
        render(<JsonTabs formatted={<JsonViewer value={value} />} raw={value} />);

        expect(screen.getByText("expression")).toBeInTheDocument();
        expect(screen.queryByText(/"expression": "2 \+ 2"/)).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole("tab", { name: "Raw JSON" }));

        expect(screen.getByText(/"expression": "2 \+ 2"/)).toBeInTheDocument();
    });
});
