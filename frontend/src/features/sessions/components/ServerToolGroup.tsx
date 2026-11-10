"use client";

import React, { useMemo, useState } from "react";
import { Server, ChevronDown, ChevronRight, ChevronsUpDown, History } from "lucide-react";
import { ToolCallRead } from "@/types";
import { ToolCallItem } from "./ToolCallItem";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/common/EmptyState";

interface ServerToolGroupProps {
    toolCalls: ToolCallRead[];
    selectedCallId?: string | null;
    onSelectCall: (call: ToolCallRead) => void;
}

interface ServerGroup {
    serverName: string;
    calls: ToolCallRead[];
    total: number;
    successful: number;
    failed: number;
    rejected: number;
}

export function ServerToolGroup({ toolCalls, selectedCallId, onSelectCall }: ServerToolGroupProps) {
    // Pure frontend grouping by server_name
    const groups: ServerGroup[] = useMemo(() => {
        const map = new Map<string, ToolCallRead[]>();
        for (const call of toolCalls) {
            const list = map.get(call.server_name) || [];
            list.push(call);
            map.set(call.server_name, list);
        }

        return Array.from(map.entries()).map(([serverName, calls]) => ({
            serverName,
            calls, // Maintains chronological ordering from the toolCalls dataset
            total: calls.length,
            successful: calls.filter((c) => c.status === "completed").length,
            failed: calls.filter((c) => c.status === "failed").length,
            rejected: calls.filter((c) => c.status === "rejected").length,
        }));
    }, [toolCalls]);

    // Track collapsed groups by server name
    const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

    const toggleGroup = (serverName: string) => {
        setCollapsedGroups((prev) => ({
            ...prev,
            [serverName]: !prev[serverName],
        }));
    };

    const allExpanded = groups.every((g) => !collapsedGroups[g.serverName]);

    const handleToggleAll = () => {
        if (allExpanded) {
            const allCollapsed: Record<string, boolean> = {};
            groups.forEach((g) => {
                allCollapsed[g.serverName] = true;
            });
            setCollapsedGroups(allCollapsed);
        } else {
            setCollapsedGroups({});
        }
    };

    if (toolCalls.length === 0) {
        return (
            <EmptyState
                icon={History}
                title="No tool executions found"
                description="This session does not have any tool calls matching your current filter criteria."
            />
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between px-1">
                <span className="text-xs text-muted-foreground font-medium">
                    Grouped by <strong className="text-foreground">{groups.length}</strong> MCP Server{groups.length === 1 ? "" : "s"}
                </span>
                <Button variant="ghost" size="sm" onClick={handleToggleAll} className="h-8 gap-1.5 text-xs text-muted-foreground">
                    <ChevronsUpDown className="h-3.5 w-3.5" />
                    {allExpanded ? "Collapse All" : "Expand All"}
                </Button>
            </div>

            <div className="space-y-3">
                {groups.map((group) => {
                    const isCollapsed = Boolean(collapsedGroups[group.serverName]);

                    return (
                        <Card key={group.serverName} className="border-border/80 overflow-hidden shadow-xs">
                            <CardHeader
                                onClick={() => toggleGroup(group.serverName)}
                                className="flex flex-row items-center justify-between p-4 cursor-pointer hover:bg-muted/40 transition-colors select-none"
                            >
                                <div className="flex items-center gap-3 min-w-0">
                                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                        <Server className="h-4 w-4" />
                                    </div>
                                    <div className="flex flex-wrap items-center gap-2 min-w-0">
                                        <CardTitle className="text-sm font-semibold text-foreground truncate">{group.serverName}</CardTitle>
                                        <Badge variant="secondary" className="font-mono text-xs">
                                            {group.total} {group.total === 1 ? "call" : "calls"}
                                        </Badge>
                                        {group.failed > 0 && (
                                            <Badge variant="destructive" className="font-mono text-[11px] py-0">
                                                {group.failed} failed
                                            </Badge>
                                        )}
                                        {group.rejected > 0 && (
                                            <Badge
                                                variant="outline"
                                                className="font-mono text-[11px] py-0 border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-400"
                                            >
                                                {group.rejected} rejected
                                            </Badge>
                                        )}
                                    </div>
                                </div>

                                <div className="flex items-center gap-2">
                                    {isCollapsed ? (
                                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                                    ) : (
                                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                    )}
                                </div>
                            </CardHeader>

                            {!isCollapsed && (
                                <CardContent className="p-4 pt-0 space-y-2 border-t border-border/40">
                                    <div className="pt-3 space-y-2.5">
                                        {group.calls.map((call) => (
                                            <ToolCallItem
                                                key={call.id}
                                                call={call}
                                                isSelected={selectedCallId === call.id}
                                                onSelect={onSelectCall}
                                                showServerName={false}
                                            />
                                        ))}
                                    </div>
                                </CardContent>
                            )}
                        </Card>
                    );
                })}
            </div>
        </div>
    );
}
