import { describe, it, expect, beforeEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { MAX_RECENTS, RECENTS_KEY, addRecent, pushRecent, useRecents, useTrackRecent } from "@/lib/recents";
import { resetLocalStoreCache } from "@/lib/local-store";

beforeEach(() => {
    window.localStorage.clear();
    resetLocalStoreCache();
});

describe("recents", () => {
    it("puts the latest visit first and drops an older visit to the same page", () => {
        const list = pushRecent(
            [
                { section: "Servers", label: "a", href: "/servers/a", at: 1 },
                { section: "Tools", label: "t", href: "/tools/t", at: 2 },
            ],
            { section: "Tools", label: "t", href: "/tools/t", at: 3 }
        );
        expect(list.map((item) => item.href)).toEqual(["/tools/t", "/servers/a"]);
    });

    it(`keeps at most ${MAX_RECENTS} entries`, () => {
        let list: ReturnType<typeof pushRecent> = [];
        for (let i = 0; i < MAX_RECENTS + 3; i += 1) {
            list = pushRecent(list, { section: "Servers", label: `s${i}`, href: `/servers/${i}`, at: i });
        }
        expect(list).toHaveLength(MAX_RECENTS);
        expect(list[0].label).toBe(`s${MAX_RECENTS + 2}`);
    });

    it("stores visits and updates subscribers", () => {
        const { result } = renderHook(() => useRecents());
        expect(result.current).toEqual([]);

        act(() => addRecent({ section: "Servers", label: "github-server", href: "/servers/s1" }));

        expect(result.current.map((item) => item.label)).toEqual(["github-server"]);
        expect(JSON.parse(window.localStorage.getItem(RECENTS_KEY) ?? "[]")[0].href).toBe("/servers/s1");
    });

    it("records a page once its label is known", () => {
        const { rerender } = renderHook(({ item }) => useTrackRecent(item), {
            initialProps: { item: null as { section: string; label: string; href: string } | null },
        });
        expect(window.localStorage.getItem(RECENTS_KEY)).toBeNull();

        rerender({ item: { section: "Tools", label: "search_issues", href: "/tools/x" } });
        expect(JSON.parse(window.localStorage.getItem(RECENTS_KEY) ?? "[]")).toHaveLength(1);
    });

    it("survives corrupt storage", () => {
        window.localStorage.setItem(RECENTS_KEY, "{not json");
        const { result } = renderHook(() => useRecents());
        expect(result.current).toEqual([]);
    });
});
