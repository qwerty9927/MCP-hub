"use client";

import React from "react";
import { Clock, LucideIcon } from "lucide-react";
import { badgeVariants } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { BACKEND_PENDING, BackendPendingId } from "@/lib/backend-pending";
import { cn } from "@/lib/utils";

interface PendingBadgeProps {
    id: BackendPendingId;
    /** Icon-only trigger (for tight spots such as the sidebar); the tooltip is the same. */
    icon?: LucideIcon;
    className?: string;
}

/** "Backend pending" badge; its tooltip names what the backend still has to provide. */
export function PendingBadge({ id, icon: Icon, className }: PendingBadgeProps) {
    const item = BACKEND_PENDING[id];
    return (
        <TooltipProvider delayDuration={150}>
            <Tooltip>
                <TooltipTrigger asChild>
                    {Icon ? (
                        <button
                            type="button"
                            data-pending-id={id}
                            aria-label={`${item.title} (backend pending)`}
                            className={cn(
                                "inline-flex h-7 w-7 shrink-0 cursor-help items-center justify-center rounded-md text-muted-foreground hover:bg-accent",
                                className
                            )}
                        >
                            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                        </button>
                    ) : (
                        <button
                            type="button"
                            data-pending-id={id}
                            aria-label={`Backend pending: ${item.title}`}
                            className={cn(
                                badgeVariants({ variant: "muted" }),
                                "shrink-0 cursor-help gap-1 whitespace-nowrap border border-border font-medium",
                                className
                            )}
                        >
                            <Clock className="h-3 w-3" aria-hidden="true" />
                            Backend pending
                        </button>
                    )}
                </TooltipTrigger>
                <TooltipContent className="max-w-xs space-y-1 text-xs">
                    <p className="font-semibold">{item.title}</p>
                    <p>
                        Waiting on: <span className="font-mono">{item.needs}</span>
                    </p>
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    );
}

interface PendingFeatureProps {
    id: BackendPendingId;
    children: React.ReactNode;
    className?: string;
}

/** Shows a designed control in place but inert and dimmed, with the pending badge beside it. */
export function PendingFeature({ id, children, className }: PendingFeatureProps) {
    return (
        <div className={cn("flex flex-wrap items-center gap-2", className)}>
            <div inert aria-disabled="true" className="pointer-events-none select-none opacity-50">
                {children}
            </div>
            <PendingBadge id={id} />
        </div>
    );
}
