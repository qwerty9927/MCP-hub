import React from "react";
import { Info, LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type CalloutTone = "info" | "warning" | "danger";

interface InfoCalloutProps {
    title: string;
    children?: React.ReactNode;
    tone?: CalloutTone;
    icon?: LucideIcon;
    /** One action on the right, e.g. a button or link. */
    action?: React.ReactNode;
    className?: string;
}

const TONES: Record<CalloutTone, { box: string; title: string; icon: string }> = {
    info: { box: "border-info-border bg-info", title: "text-info-foreground", icon: "text-primary" },
    warning: { box: "border-warning/30 bg-warning/10", title: "text-warning", icon: "text-warning" },
    danger: { box: "border-danger/40 bg-destructive/10", title: "text-danger", icon: "text-danger" },
};

/** Tinted band that explains a state and offers one action. It informs; it is not a toast. */
export function InfoCallout({ title, children, tone = "info", icon: Icon = Info, action, className }: InfoCalloutProps) {
    const styles = TONES[tone];
    return (
        <div className={cn("flex flex-wrap items-start gap-x-4 gap-y-3 rounded-xl border px-5 py-4", styles.box, className)}>
            <Icon className={cn("mt-0.5 h-[18px] w-[18px] shrink-0", styles.icon)} aria-hidden="true" />
            <div className="min-w-0 flex-[1_1_320px] space-y-0.5">
                <p className={cn("text-sm font-semibold", styles.title)}>{title}</p>
                {children && <div className="text-sm text-foreground/85">{children}</div>}
            </div>
            {action && <div className="shrink-0 self-center">{action}</div>}
        </div>
    );
}
