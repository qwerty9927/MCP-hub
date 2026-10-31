import React from "react";
import { Badge } from "@/components/ui/badge";
import { ServerHealthStatus } from "@/types";
import { cn } from "@/lib/utils";

interface HealthBadgeProps {
    status: ServerHealthStatus | string;
    className?: string;
}

export function HealthBadge({ status, className }: HealthBadgeProps) {
    const normalized = status.toUpperCase();

    switch (normalized) {
        case "HEALTHY":
        case "AVAILABLE":
            return (
                <Badge
                    variant="success"
                    className={cn("gap-1.5 font-medium px-2 py-0.5", className)}
                >
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    {normalized === "AVAILABLE" ? "Available" : "Healthy"}
                </Badge>
            );
        case "CONNECTING":
            return (
                <Badge
                    variant="warning"
                    className={cn("gap-1.5 font-medium px-2 py-0.5", className)}
                >
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                    Connecting
                </Badge>
            );
        case "UNHEALTHY":
        case "UNAVAILABLE":
            return (
                <Badge
                    variant="destructive"
                    className={cn("gap-1.5 font-medium px-2 py-0.5", className)}
                >
                    <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
                    {normalized === "UNAVAILABLE" ? "Unavailable" : "Unhealthy"}
                </Badge>
            );
        case "DISCONNECTED":
            return (
                <Badge
                    variant="secondary"
                    className={cn(
                        "gap-1.5 font-medium px-2 py-0.5 text-muted-foreground",
                        className
                    )}
                >
                    <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
                    Disconnected
                </Badge>
            );
        default:
            return (
                <Badge variant="muted" className={cn("gap-1.5 font-medium px-2 py-0.5", className)}>
                    <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
                    {status || "Unknown"}
                </Badge>
            );
    }
}
