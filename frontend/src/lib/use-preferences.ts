"use client";

import { useCallback } from "react";
import { writeLocal } from "./local-store";
import { useLocalValue } from "./use-local-value";
import { PREFERENCES_KEY, Preferences, mergePreferences, readPreferences } from "./preferences";

/** The console preferences and a setter that merges a patch into them. */
export function usePreferences(): [Preferences, (patch: Partial<Preferences>) => void] {
    const stored = useLocalValue<Partial<Preferences> | null>(PREFERENCES_KEY, null);
    const update = useCallback((patch: Partial<Preferences>) => writeLocal(PREFERENCES_KEY, { ...readPreferences(), ...patch }), []);
    return [mergePreferences(stored), update];
}
