import React from "react";
import { cn } from "@/lib/utils";

interface EmptyChartProps {
    /** Pill text over the ghost line, e.g. "No failures in this range". */
    label: string;
    /** Extra content next to the pill (e.g. a pending badge). */
    children?: React.ReactNode;
    className?: string;
}

/** Keeps a chart's footprint when there is nothing to plot: a faint line and an honest pill. */
export function EmptyChart({ label, children, className }: EmptyChartProps) {
    return (
        <div className={cn("relative mt-2 flex h-36 items-center justify-center", className)}>
            <svg aria-hidden="true" viewBox="0 0 400 120" preserveAspectRatio="none" className="absolute inset-0 h-full w-full text-border">
                <path
                    d="M0 70 C 40 60, 70 85, 110 72 S 170 50, 210 66 S 280 90, 320 62 S 370 58, 400 74"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                />
            </svg>
            <div className="relative flex flex-wrap items-center justify-center gap-2">
                <span className="rounded-full border border-border bg-card px-2.5 py-0.5 text-xs text-muted-foreground">{label}</span>
                {children}
            </div>
        </div>
    );
}
