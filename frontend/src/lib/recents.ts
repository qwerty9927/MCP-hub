"use client";

import { useEffect } from "react";
import { readLocal, writeLocal } from "./local-store";
import { useLocalValue } from "./use-local-value";

/** A page the user opened, shown on the Overview as "Section / Label". */
export interface RecentItem {
    section: string;
    label: string;
    href: string;
    /** Epoch ms of the last visit. */
    at: number;
}

export const RECENTS_KEY = "mcp-hub:recents";
export const MAX_RECENTS = 8;
const EMPTY: RecentItem[] = [];

/** Puts the item first, removing an older visit to the same href, and keeps at most MAX_RECENTS. */
export function pushRecent(list: RecentItem[], item: RecentItem): RecentItem[] {
    return [item, ...list.filter((entry) => entry.href !== item.href)].slice(0, MAX_RECENTS);
}

export function addRecent(item: Omit<RecentItem, "at">): void {
    const list = readLocal<RecentItem[]>(RECENTS_KEY, EMPTY);
    writeLocal(RECENTS_KEY, pushRecent(Array.isArray(list) ? list : EMPTY, { ...item, at: Date.now() }));
}

export function useRecents(): RecentItem[] {
    const list = useLocalValue<RecentItem[]>(RECENTS_KEY, EMPTY);
    return Array.isArray(list) ? list : EMPTY;
}

/** Records a visit once the page knows its label; pass null while it is loading. */
export function useTrackRecent(item: Omit<RecentItem, "at"> | null): void {
    const section = item?.section;
    const label = item?.label;
    const href = item?.href;
    useEffect(() => {
        if (section && label && href) addRecent({ section, label, href });
    }, [section, label, href]);
}
