"use client";

import { useCallback, useSyncExternalStore } from "react";
import { localSnapshot, subscribeLocal } from "./local-store";

/** Reactive value of a localStorage key; `fallback` must be a stable (module-level) value. */
export function useLocalValue<T>(key: string, fallback: T): T {
    const subscribe = useCallback((onChange: () => void) => subscribeLocal(key, onChange), [key]);
    return useSyncExternalStore(
        subscribe,
        () => localSnapshot(key, fallback),
        () => fallback
    );
}
