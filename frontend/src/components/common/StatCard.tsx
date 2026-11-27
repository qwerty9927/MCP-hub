import React from "react";
import { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface StatCardProps {
    title: string;
    value: React.ReactNode;
    /** Qualifier under the value, e.g. "4 healthy · 3 need auth". */
    footnote?: React.ReactNode;
    icon?: LucideIcon;
    iconClassName?: string;
    /** Rendered after the value, e.g. a delta or a pending badge. */
    valueAddon?: React.ReactNode;
    /** Top-right slot (overflow menu, badge); replaces the icon. */
    action?: React.ReactNode;
    loading?: boolean;
    children?: React.ReactNode;
    className?: string;
}

/** Metric card: noun title, mono value, footnote; optional body (chart) below. */
export function StatCard({
    title,
    value,
    footnote,
    icon: Icon,
    iconClassName,
    valueAddon,
    action,
    loading,
    children,
    className,
}: StatCardProps) {
    return (
        <Card className={cn("flex flex-col gap-2 px-6 py-5", className)}>
            <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-medium leading-none text-foreground">{title}</h3>
                {action ?? (Icon && <Icon className={cn("h-4 w-4 text-muted-foreground", iconClassName)} aria-hidden="true" />)}
            </div>
            {loading ? (
                <Skeleton className="h-8 w-20" />
            ) : (
                <div className="flex flex-wrap items-baseline gap-2">
                    <span className="font-mono text-2xl font-bold leading-8">{value}</span>
                    {valueAddon}
                </div>
            )}
            {footnote && <div className="text-xs text-muted-foreground">{footnote}</div>}
            {children}
        </Card>
    );
}
