import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { preferredTimeZone } from "./preferences";

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

/** Recorded status of an execution, falling back to `is_error` for records without one. */
export function executionStatus(execution: { status?: string | null; is_error: boolean }): string {
    return execution.status || (execution.is_error ? "failed" : "completed");
}

export function formatDate(dateStr: string | null | undefined): string {
    if (!dateStr) return "Never";
    try {
        const date = new Date(dateStr);
        return new Intl.DateTimeFormat("en-US", {
            dateStyle: "medium",
            timeStyle: "short",
            // The time zone chosen in Settings, else the browser's own.
            timeZone: preferredTimeZone(),
        }).format(date);
    } catch {
        return dateStr;
    }
}

export function formatDuration(ms: number | null | undefined): string {
    if (ms === null || ms === undefined) return "-";
    if (ms < 1) return `${(ms * 1000).toFixed(0)}µs`;
    if (ms < 1000) return `${ms.toFixed(1)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
}

const SECONDS_PER_MINUTE = 60;

/** A wait in seconds as words: "45 seconds", "1 minute", "2 minutes" (minutes round up, so the wait is never understated). */
export function formatRetryAfter(seconds: number): string {
    if (seconds < SECONDS_PER_MINUTE) return seconds === 1 ? "1 second" : `${seconds} seconds`;
    const minutes = Math.ceil(seconds / SECONDS_PER_MINUTE);
    return minutes === 1 ? "1 minute" : `${minutes} minutes`;
}
