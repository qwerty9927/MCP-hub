import { describe, it, expect } from "vitest";
import { serverFormSchema } from "@/schemas/server.schema";

describe("Server Form Schema Validation", () => {
    it("validates a valid stdio configuration", () => {
        const validStdio = {
            name: "local-math",
            description: "Math tools",
            transport: "stdio",
            enabled: true,
            stdio_command: "python3",
            stdio_args: "-m demo_server.server",
            stdio_env: "",
            http_url: "",
            http_headers: "",
        };

        const result = serverFormSchema.safeParse(validStdio);
        expect(result.success).toBe(true);
    });

    it("fails if stdio command is missing when transport is stdio", () => {
        const invalidStdio = {
            name: "local-math",
            description: "Math tools",
            transport: "stdio",
            enabled: true,
            stdio_command: "",
            stdio_args: "",
            stdio_env: "",
            http_url: "",
            http_headers: "",
        };

        const result = serverFormSchema.safeParse(invalidStdio);
        expect(result.success).toBe(false);
        if (!result.success) {
            const commandIssue = result.error.issues.find((i) => i.path.includes("stdio_command"));
            expect(commandIssue).toBeDefined();
        }
    });

    it("validates a valid streamable-http configuration", () => {
        const validHttp = {
            name: "remote-tools",
            description: "Remote HTTP MCP Server",
            transport: "streamable-http",
            enabled: true,
            stdio_command: "",
            stdio_args: "",
            stdio_env: "",
            http_url: "https://mcp.internal.example.com/mcp",
            http_headers: '{"Authorization": "Bearer token"}',
        };

        const result = serverFormSchema.safeParse(validHttp);
        expect(result.success).toBe(true);
    });

    it("fails if http_url is missing or invalid for streamable-http", () => {
        const invalidHttp = {
            name: "remote-tools",
            transport: "streamable-http",
            enabled: true,
            http_url: "invalid-url",
        };

        const result = serverFormSchema.safeParse(invalidHttp);
        expect(result.success).toBe(false);
    });

    it("rejects server names with spaces or invalid special characters", () => {
        const invalidName = {
            name: "invalid name with spaces!",
            transport: "stdio",
            stdio_command: "node",
        };

        const result = serverFormSchema.safeParse(invalidName);
        expect(result.success).toBe(false);
    });
});
