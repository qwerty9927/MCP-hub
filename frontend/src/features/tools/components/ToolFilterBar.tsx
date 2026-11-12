"use client";

import React from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToolFilterParams } from "@/types";
import { useServers } from "@/features/servers/hooks/use-servers";

interface ToolFilterBarProps {
    filters: ToolFilterParams;
    onChange: (updated: ToolFilterParams) => void;
}

export function ToolFilterBar({ filters, onChange }: ToolFilterBarProps) {
    const { data: serversData } = useServers({ page: 1, page_size: 100 });
    const servers = serversData?.items || [];

    const hasActiveFilters = Boolean(filters.search || filters.server_id || filters.status);

    const handleClear = () => {
        onChange({
            page: 1,
            page_size: filters.page_size,
            search: undefined,
            server_id: undefined,
            status: undefined,
        });
    };

    return (
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between py-2">
            <div className="flex flex-1 flex-wrap items-center gap-2">
                {/* Search */}
                <div className="relative min-w-[200px] flex-1 max-w-sm">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        aria-label="Search tools"
                        placeholder="Search tools by name, description, server..."
                        value={filters.search || ""}
                        onChange={(e) =>
                            onChange({
                                ...filters,
                                search: e.target.value || undefined,
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
                    <SelectTrigger className="h-9 w-[180px]" aria-label="Filter by server">
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

                {/* Availability Status Filter */}
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
                    <SelectTrigger className="h-9 w-[150px]" aria-label="Filter by status">
                        <SelectValue placeholder="Availability" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Statuses</SelectItem>
                        <SelectItem value="AVAILABLE">Available</SelectItem>
                        <SelectItem value="UNAVAILABLE">Unavailable</SelectItem>
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
