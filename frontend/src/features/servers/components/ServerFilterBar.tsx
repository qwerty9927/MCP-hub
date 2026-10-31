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
import { ServerFilterParams, ServerHealthStatus, TransportType } from "@/types";

interface ServerFilterBarProps {
    filters: ServerFilterParams;
    onChange: (updated: ServerFilterParams) => void;
}

export function ServerFilterBar({ filters, onChange }: ServerFilterBarProps) {
    const hasActiveFilters = Boolean(
        filters.search ||
        filters.transport ||
        filters.health_status ||
        filters.enabled !== undefined
    );

    const handleClear = () => {
        onChange({
            page: 1,
            page_size: filters.page_size,
            search: undefined,
            transport: undefined,
            health_status: undefined,
            enabled: undefined,
            sort_by: "created_at",
            sort_order: "desc",
        });
    };

    return (
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between py-2">
            <div className="flex flex-1 flex-wrap items-center gap-2">
                {/* Search */}
                <div className="relative min-w-[200px] flex-1 max-w-sm">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search servers by name..."
                        value={filters.search || ""}
                        onChange={(e) =>
                            onChange({ ...filters, search: e.target.value || undefined, page: 1 })
                        }
                        className="pl-8 h-9"
                    />
                </div>

                {/* Transport Filter */}
                <Select
                    value={filters.transport || "all"}
                    onValueChange={(val) =>
                        onChange({
                            ...filters,
                            transport: val === "all" ? undefined : (val as TransportType),
                            page: 1,
                        })
                    }
                >
                    <SelectTrigger className="h-9 w-[140px]">
                        <SelectValue placeholder="Transport" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Transports</SelectItem>
                        <SelectItem value="stdio">stdio</SelectItem>
                        <SelectItem value="streamable-http">HTTP</SelectItem>
                    </SelectContent>
                </Select>

                {/* Health Status Filter */}
                <Select
                    value={filters.health_status || "all"}
                    onValueChange={(val) =>
                        onChange({
                            ...filters,
                            health_status: val === "all" ? undefined : (val as ServerHealthStatus),
                            page: 1,
                        })
                    }
                >
                    <SelectTrigger className="h-9 w-[150px]">
                        <SelectValue placeholder="Status" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Statuses</SelectItem>
                        <SelectItem value="HEALTHY">Healthy</SelectItem>
                        <SelectItem value="UNHEALTHY">Unhealthy</SelectItem>
                        <SelectItem value="CONNECTING">Connecting</SelectItem>
                        <SelectItem value="DISCONNECTED">Disconnected</SelectItem>
                        <SelectItem value="UNKNOWN">Unknown</SelectItem>
                    </SelectContent>
                </Select>

                {/* Enabled Filter */}
                <Select
                    value={
                        filters.enabled === undefined
                            ? "all"
                            : filters.enabled
                              ? "enabled"
                              : "disabled"
                    }
                    onValueChange={(val) =>
                        onChange({
                            ...filters,
                            enabled: val === "all" ? undefined : val === "enabled" ? true : false,
                            page: 1,
                        })
                    }
                >
                    <SelectTrigger className="h-9 w-[130px]">
                        <SelectValue placeholder="Enabled" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All States</SelectItem>
                        <SelectItem value="enabled">Enabled</SelectItem>
                        <SelectItem value="disabled">Disabled</SelectItem>
                    </SelectContent>
                </Select>

                {/* Reset Filter Button */}
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

            {/* Sorting */}
            <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground whitespace-nowrap">Sort by:</span>
                <Select
                    value={`${filters.sort_by || "created_at"}_${filters.sort_order || "desc"}`}
                    onValueChange={(val) => {
                        const [field, order] = val.split("_");
                        onChange({
                            ...filters,
                            sort_by: field as any,
                            sort_order: order as any,
                        });
                    }}
                >
                    <SelectTrigger className="h-9 w-[170px]">
                        <SelectValue placeholder="Sort" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="created_at_desc">Newest First</SelectItem>
                        <SelectItem value="created_at_asc">Oldest First</SelectItem>
                        <SelectItem value="name_asc">Name (A-Z)</SelectItem>
                        <SelectItem value="name_desc">Name (Z-A)</SelectItem>
                        <SelectItem value="discovered_tool_count_desc">Most Tools</SelectItem>
                    </SelectContent>
                </Select>
            </div>
        </div>
    );
}
