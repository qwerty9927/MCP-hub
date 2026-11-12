"use client";

import React from "react";
import { Wrench, Server, Clock, ChevronRight } from "lucide-react";
import { ToolCallRead } from "@/types";
import { Badge } from "@/components/ui/badge";
import { cn, formatDate, formatDuration } from "@/lib/utils";
import { ToolCallStatusBadge } from "@/components/common/ToolCallStatusBadge";

interface ToolCallItemProps {
    call: ToolCallRead;
    isSelected?: boolean;
    onSelect: (call: ToolCallRead) => void;
    showServerName?: boolean;
}

export function ToolCallItem({ call, isSelected = false, onSelect, showServerName = true }: ToolCallItemProps) {
    return (
        <div
            onClick={() => onSelect(call)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(call);
                }
            }}
            className={cn(
                "group relative flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border p-3.5 text-left transition-all cursor-pointer",
                isSelected
                    ? "border-primary bg-primary/5 shadow-sm ring-1 ring-primary/30"
                    : "border-border bg-card hover:border-primary/50 hover:bg-muted/40"
            )}
        >
            <div className="flex items-start sm:items-center gap-3 min-w-0">
                <div
                    className={cn(
                        "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors",
                        call.status === "failed"
                            ? "bg-destructive/10 text-destructive"
                            : call.status === "rejected"
                              ? "bg-orange-500/10 text-orange-600 dark:text-orange-400"
                              : call.status === "running"
                                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                                : "bg-primary/10 text-primary"
                    )}
                >
                    <Wrench className="h-4 w-4" />
                </div>

                <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-sm text-foreground group-hover:text-primary transition-colors truncate">
                            {call.tool_name}
                        </span>
                        {showServerName && (
                            <Badge variant="outline" className="gap-1 text-[11px] font-normal text-muted-foreground py-0">
                                <Server className="h-3 w-3 text-primary" />
                                {call.server_name}
                            </Badge>
                        )}
                    </div>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground mt-1">
                        <span className="flex items-center gap-1 font-mono">
                            <Clock className="h-3 w-3" />
                            {formatDate(call.started_at)}
                        </span>
                        <span className="font-mono">{formatDuration(call.duration_ms)}</span>
                    </div>
                </div>
            </div>

            <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-border/50">
                <ToolCallStatusBadge status={call.status} className="gap-1.5 py-0.5" />
                <ChevronRight className="h-4 w-4 text-muted-foreground opacity-60 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
            </div>
        </div>
    );
}
