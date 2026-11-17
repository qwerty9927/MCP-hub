import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient } from "@/lib/api-client";
import { serversApi, TOOLS_PAGE_SIZE } from "@/lib/api/servers";

vi.mock("@/lib/api-client", () => ({ apiClient: vi.fn() }));

const SERVER_ID = "0b7f6c1e-5d2a-4c8e-9f31-2a6d4e8b7c90";

function tools(from: number, count: number) {
    return Array.from({ length: count }, (_, index) => ({ id: `tool-${from + index}`, name: `tool_${from + index}` }));
}

describe("serversApi.getAllTools", () => {
    beforeEach(() => {
        vi.mocked(apiClient).mockReset();
    });

    it("asks for the largest page and stops after one request when everything fits", async () => {
        vi.mocked(apiClient).mockResolvedValueOnce({ items: tools(0, 46), total: 46, page: 1, page_size: TOOLS_PAGE_SIZE, total_pages: 1 });

        const result = await serversApi.getAllTools(SERVER_ID);

        expect(result).toHaveLength(46);
        expect(apiClient).toHaveBeenCalledTimes(1);
        expect(apiClient).toHaveBeenCalledWith(
            expect.objectContaining({ url: `/servers/${SERVER_ID}/tools`, params: { page: 1, page_size: TOOLS_PAGE_SIZE } })
        );
    });

    it("follows the pages until it has the total", async () => {
        vi.mocked(apiClient)
            .mockResolvedValueOnce({ items: tools(0, 100), total: 130, page: 1, page_size: 100, total_pages: 2 })
            .mockResolvedValueOnce({ items: tools(100, 30), total: 130, page: 2, page_size: 100, total_pages: 2 });

        const result = await serversApi.getAllTools(SERVER_ID);

        expect(result.map((tool) => tool.id)).toEqual(tools(0, 130).map((tool) => tool.id));
        expect(apiClient).toHaveBeenNthCalledWith(2, expect.objectContaining({ params: { page: 2, page_size: TOOLS_PAGE_SIZE } }));
    });

    it("stops on an empty page even if the total says more", async () => {
        vi.mocked(apiClient)
            .mockResolvedValueOnce({ items: tools(0, 100), total: 150, page: 1, page_size: 100, total_pages: 2 })
            .mockResolvedValueOnce({ items: [], total: 150, page: 2, page_size: 100, total_pages: 2 });

        expect(await serversApi.getAllTools(SERVER_ID)).toHaveLength(100);
        expect(apiClient).toHaveBeenCalledTimes(2);
    });
});
