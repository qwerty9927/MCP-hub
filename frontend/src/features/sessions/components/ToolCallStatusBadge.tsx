import React from "react";
import { Ban, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ToolCallStatusBadgeProps {
    status: string;
    className?: string;
}

/** Status badge for a tool call; `rejected` = refused by the hub before reaching the downstream Server (ADR-0002). */
export function ToolCallStatusBadge({ status, className }: ToolCallStatusBadgeProps) {
    const classes = cn("gap-1 text-xs", className);
    switch (status.toLowerCase()) {
        case "completed":
            return (
                <Badge variant="success" className={classes}>
                    <CheckCircle2 className="h-3 w-3" />
                    Completed
                </Badge>
            );
        case "failed":
            return (
                <Badge variant="destructive" className={classes}>
                    <XCircle className="h-3 w-3" />
                    Failed
                </Badge>
            );
        case "rejected":
            return (
                <Badge
                    variant="outline"
                    className={cn("border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-400", classes)}
                >
                    <Ban className="h-3 w-3" />
                    Rejected
                </Badge>
            );
        case "running":
            return (
                <Badge variant="warning" className={classes}>
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Running
                </Badge>
            );
        default:
            return <Badge variant="outline">{status}</Badge>;
    }
}
