import { readLocal } from "./local-store";

/**
 * Per-browser console preferences. Server-side preferences are pending (see lib/backend-pending.ts).
 * Hook-free so formatDate can use it; the React hook is in use-preferences.ts.
 */
export interface Preferences {
    /** ⌘K / Ctrl+K opens quick search. */
    keyboardShortcuts: boolean;
    /** IANA time zone for dates; null = the browser's own. */
    timeZone: string | null;
}

export const PREFERENCES_KEY = "mcp-hub:preferences";

export const DEFAULT_PREFERENCES: Preferences = { keyboardShortcuts: true, timeZone: null };

export function mergePreferences(stored: Partial<Preferences> | null | undefined): Preferences {
    return { ...DEFAULT_PREFERENCES, ...(stored ?? {}) };
}

export function readPreferences(): Preferences {
    return mergePreferences(readLocal<Partial<Preferences> | null>(PREFERENCES_KEY, null));
}

export function isValidTimeZone(timeZone: string): boolean {
    try {
        new Intl.DateTimeFormat("en-US", { timeZone });
        return true;
    } catch {
        return false;
    }
}

/** The preferred time zone when it is set and valid, else undefined (the browser's own). */
export function preferredTimeZone(): string | undefined {
    const { timeZone } = readPreferences();
    return timeZone && isValidTimeZone(timeZone) ? timeZone : undefined;
}
