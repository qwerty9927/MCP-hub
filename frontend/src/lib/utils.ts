import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

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
