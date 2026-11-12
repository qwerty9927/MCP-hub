"use client";

import React from "react";
import { Search, X, RefreshCw } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ExecutionFilterParams } from "@/types";
import { useServers } from "@/features/servers/hooks/use-servers";
import { cn } from "@/lib/utils";

interface ExecutionFilterBarProps {
    filters: ExecutionFilterParams;
    onChange: (updated: ExecutionFilterParams) => void;
    onRefresh?: () => void;
    isRefreshing?: boolean;
    autoRefresh?: boolean;
    onToggleAutoRefresh?: (enabled: boolean) => void;
}

export function ExecutionFilterBar({
    filters,
    onChange,
    onRefresh,
    isRefreshing = false,
    autoRefresh = false,
    onToggleAutoRefresh,
}: ExecutionFilterBarProps) {
    const { data: serversData } = useServers({ page: 1, page_size: 100 });
    const servers = serversData?.items || [];

    const hasActiveFilters = Boolean(filters.tool_name || filters.server_id || filters.status);

    const handleClear = () => {
        onChange({
            page: 1,
            page_size: filters.page_size,
            tool_name: undefined,
            server_id: undefined,
            status: undefined,
        });
    };

    return (
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between py-2">
            <div className="flex flex-1 flex-wrap items-center gap-2">
                {/* Tool Name Filter */}
                <div className="relative min-w-[200px] flex-1 max-w-sm">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Filter by tool name..."
                        value={filters.tool_name || ""}
                        onChange={(e) =>
                            onChange({
                                ...filters,
                                tool_name: e.target.value || undefined,
                                page: 1,
                            })
                        }
                        className="pl-8 h-9"
                    />
                </div>

                {/* Server Filter */}
                <Select
                    value={filters.server_id || "all"}
                    onValueChange={(val) =>
                        onChange({
                            ...filters,
                            server_id: val === "all" ? undefined : val,
                            page: 1,
                        })
                    }
                >
                    <SelectTrigger className="h-9 w-[180px]">
                        <SelectValue placeholder="All Servers" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Servers</SelectItem>
                        {servers.map((s) => (
                            <SelectItem key={s.id} value={s.id}>
                                {s.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>

                {/* Status Filter */}
                <Select
                    value={filters.status || "all"}
                    onValueChange={(val) =>
                        onChange({
                            ...filters,
                            status: val === "all" ? undefined : val,
                            page: 1,
                        })
                    }
                >
                    <SelectTrigger className="h-9 w-[140px]">
                        <SelectValue placeholder="All Status" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Status</SelectItem>
                        <SelectItem value="completed">Completed</SelectItem>
                        <SelectItem value="failed">Failed</SelectItem>
                        <SelectItem value="rejected">Rejected</SelectItem>
                    </SelectContent>
                </Select>

                {hasActiveFilters && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleClear}
                        className="h-9 px-2 text-xs text-muted-foreground hover:text-foreground"
                    >
                        <X className="mr-1 h-3.5 w-3.5" />
                        Reset
                    </Button>
                )}
            </div>

            {/* Live refresh controls */}
            <div className="flex items-center gap-3">
                {onToggleAutoRefresh && (
                    <div className="flex items-center gap-2">
                        <Switch
                            id="auto-refresh-toggle"
                            checked={autoRefresh}
                            onCheckedChange={onToggleAutoRefresh}
                            aria-label="Toggle auto refresh"
                        />
                        <label
                            htmlFor="auto-refresh-toggle"
                            className="text-xs text-muted-foreground cursor-pointer select-none flex items-center gap-1.5"
                        >
                            <span
                                className={cn(
                                    "h-1.5 w-1.5 rounded-full transition-colors",
                                    autoRefresh ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground/40"
                                )}
                            />
                            Live (10s)
                        </label>
                    </div>
                )}

                {onRefresh && (
                    <Button variant="outline" size="sm" onClick={onRefresh} disabled={isRefreshing} className="h-9 gap-1.5 text-xs">
                        <RefreshCw className={cn("h-3.5 w-3.5", isRefreshing && "animate-spin text-primary")} />
                        Refresh
                    </Button>
                )}
            </div>
        </div>
    );
}
