import { describe, it, expect } from "vitest";
import { API_BASE_URL, API_PROXY_PATH, MCP_ENDPOINT_URL } from "@/lib/config";
import { axiosInstance } from "@/lib/api-client";

// vitest.config.ts sets NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
describe("console API proxy", () => {
    it("sends the console's own calls to the same-origin proxy path", () => {
        expect(API_PROXY_PATH).toBe("/api/v1");
        expect(axiosInstance.defaults.baseURL).toBe("/api/v1");
    });

    it("keeps the backend's public address for what users copy", () => {
        expect(API_BASE_URL).toBe("http://localhost:8000/api/v1");
        expect(MCP_ENDPOINT_URL).toBe("http://localhost:8000/mcp");
    });
});
