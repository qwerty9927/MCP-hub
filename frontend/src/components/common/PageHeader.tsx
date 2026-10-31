import React from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
    title: string;
    description?: string;
    actions?: React.ReactNode;
    className?: string;
    children?: React.ReactNode;
}

export function PageHeader({ title, description, actions, className, children }: PageHeaderProps) {
    return (
        <div
            className={cn(
                "flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between pb-6 border-b border-border mb-6",
                className
            )}
        >
            <div className="space-y-1">
                <h1 className="text-2xl font-bold tracking-tight text-foreground">{title}</h1>
                {description && <p className="text-sm text-muted-foreground">{description}</p>}
            </div>
            {(actions || children) && (
                <div className="flex flex-wrap items-center gap-2">
                    {actions}
                    {children}
                </div>
            )}
        </div>
    );
}
