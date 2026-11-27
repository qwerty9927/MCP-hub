"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface SegmentedOption<T extends string> {
    value: T;
    label: React.ReactNode;
    disabled?: boolean;
}

interface SegmentedControlProps<T extends string> {
    /** Accessible name of the group, e.g. "Time range". */
    label: string;
    value: T;
    onValueChange: (value: T) => void;
    options: SegmentedOption<T>[];
    className?: string;
}

/** A small set of mutually exclusive toggle buttons (time range, metric). */
export function SegmentedControl<T extends string>({ label, value, onValueChange, options, className }: SegmentedControlProps<T>) {
    return (
        <div role="group" aria-label={label} className={cn("inline-flex gap-0.5 rounded-lg bg-muted p-[3px]", className)}>
            {options.map((option) => {
                const active = option.value === value;
                return (
                    <button
                        key={option.value}
                        type="button"
                        aria-pressed={active}
                        disabled={option.disabled}
                        onClick={() => onValueChange(option.value)}
                        className={cn(
                            "inline-flex h-[30px] items-center gap-1.5 rounded-md border px-3 text-[13px] transition-colors",
                            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
                            active
                                ? "border-border bg-card font-semibold text-foreground shadow-sm"
                                : "border-transparent font-medium text-muted-foreground hover:text-foreground"
                        )}
                    >
                        {option.label}
                    </button>
                );
            })}
        </div>
    );
}
