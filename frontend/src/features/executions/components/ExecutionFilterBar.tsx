"use client";

import React from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { ExecutionFilterParams } from "@/types";
import { useServers } from "@/features/servers/hooks/use-servers";

interface ExecutionFilterBarProps {
    filters: ExecutionFilterParams;
    onChange: (updated: ExecutionFilterParams) => void;
}

export function ExecutionFilterBar({ filters, onChange }: ExecutionFilterBarProps) {
    const { data: serversData } = useServers({ page: 1, page_size: 100 });
    const servers = serversData?.items || [];

    const hasActiveFilters = Boolean(
        filters.tool_name || filters.server_id || filters.is_error !== undefined
    );

    const handleClear = () => {
        onChange({
            page: 1,
            page_size: filters.page_size,
            tool_name: undefined,
            server_id: undefined,
            is_error: undefined,
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
                    value={
                        filters.is_error === undefined
                            ? "all"
                            : filters.is_error
                              ? "error"
                              : "success"
                    }
                    onValueChange={(val) =>
                        onChange({
                            ...filters,
                            is_error: val === "all" ? undefined : val === "error" ? true : false,
                            page: 1,
                        })
                    }
                >
                    <SelectTrigger className="h-9 w-[140px]">
                        <SelectValue placeholder="All Status" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Status</SelectItem>
                        <SelectItem value="success">Success</SelectItem>
                        <SelectItem value="error">Failed</SelectItem>
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
        </div>
    );
}
