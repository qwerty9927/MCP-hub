import React from "react";
import { cn } from "@/lib/utils";

interface SettingsRowProps {
    label: React.ReactNode;
    /** Id of the control the label names, so the label is a real <label>. */
    htmlFor?: string;
    description?: React.ReactNode;
    children?: React.ReactNode;
    className?: string;
}

/** One settings row: label (and description) on the left, the control on the right. */
export function SettingsRow({ label, htmlFor, description, children, className }: SettingsRowProps) {
    const Label = htmlFor ? "label" : "span";
    return (
        <div
            className={cn(
                "flex min-h-14 flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3 first:border-t-0",
                className
            )}
        >
            <div className="flex min-w-0 flex-[1_1_280px] flex-col gap-0.5">
                <Label htmlFor={htmlFor} className="text-sm font-medium">
                    {label}
                </Label>
                {description && <span className="text-[13px] text-muted-foreground">{description}</span>}
            </div>
            {children && <div className="flex shrink-0 items-center gap-2">{children}</div>}
        </div>
    );
}

/** Titled group of settings rows. */
export function SettingsGroup({ title, children }: { title: string; children: React.ReactNode }) {
    const id = `settings-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
    return (
        <section aria-labelledby={id} className="flex flex-col gap-2.5">
            <h2 id={id} className="text-sm font-semibold">
                {title}
            </h2>
            <div className="rounded-xl border border-border bg-card shadow-sm">{children}</div>
        </section>
    );
}
