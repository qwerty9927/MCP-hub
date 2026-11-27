/**
 * Small JSON store in localStorage for per-browser conveniences (preferences, recents). No React here, so server
 * code (e.g. formatDate) can import it; the hook lives in use-local-value.ts.
 * Storage can be missing or throw (private windows, blocked site data): reads fall back to the default and
 * writes are best-effort. Changes are broadcast in this tab with a custom event and across tabs by "storage".
 */
const CHANGE_EVENT = "mcp-hub:local-store";

function read<T>(key: string, fallback: T): T {
    try {
        const raw = window.localStorage.getItem(key);
        return raw ? (JSON.parse(raw) as T) : fallback;
    } catch {
        return fallback;
    }
}

// useSyncExternalStore needs a stable snapshot per change, so parsed values are cached by key.
const snapshots = new Map<string, unknown>();
// Values written while storage is unavailable still apply for this page's lifetime.
const memory = new Map<string, unknown>();

export function readLocal<T>(key: string, fallback: T): T {
    if (typeof window === "undefined") return fallback;
    const stored = read<T | undefined>(key, undefined);
    if (stored !== undefined) return stored;
    return memory.has(key) ? (memory.get(key) as T) : fallback;
}

export function writeLocal<T>(key: string, value: T): void {
    if (typeof window === "undefined") return;
    try {
        window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
        // Best-effort: the in-memory copy below still applies for this page.
    }
    snapshots.delete(key);
    memory.set(key, value);
    window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: key }));
}

/** Cached value for useSyncExternalStore; recomputed only after a change to `key`. */
export function localSnapshot<T>(key: string, fallback: T): T {
    if (!snapshots.has(key)) snapshots.set(key, readLocal(key, fallback));
    return snapshots.get(key) as T;
}

/** Calls `onChange` when `key` changes in this tab or another one. */
export function subscribeLocal(key: string, onChange: () => void): () => void {
    const handle = (event: Event) => {
        const changed = event instanceof StorageEvent ? event.key : (event as CustomEvent<string>).detail;
        if (changed === key || changed === null) {
            snapshots.delete(key);
            onChange();
        }
    };
    window.addEventListener(CHANGE_EVENT, handle);
    window.addEventListener("storage", handle);
    return () => {
        window.removeEventListener(CHANGE_EVENT, handle);
        window.removeEventListener("storage", handle);
    };
}

/** Test helper: forget cached snapshots and in-memory values. */
export function resetLocalStoreCache(): void {
    snapshots.clear();
    memory.clear();
}
