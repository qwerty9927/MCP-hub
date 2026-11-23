"use client";

import React from "react";
import Link from "next/link";
import { ToolUsage } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { historyServerHref } from "@/lib/server-links";
import { formatDate, formatDuration } from "@/lib/utils";
import { formatPercent, toolUsageKey } from "@/features/metrics/utils";

export const TOOL_USAGE_COLUMNS = ["#", "Tool", "Calls", "Share", "Success rate", "Avg duration", "Last used"];

interface ToolUsageTableProps {
    items: ToolUsage[];
    /** Every call in the range; the denominator for each tool's share. */
    totalCalls: number;
}

export function ToolUsageTable({ items, totalCalls }: ToolUsageTableProps) {
    return (
        <div className="rounded-md border border-border bg-card">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead className="w-12">#</TableHead>
                        <TableHead>Tool</TableHead>
                        <TableHead className="text-right">Calls</TableHead>
                        <TableHead className="text-right">Share</TableHead>
                        <TableHead className="text-right">Success rate</TableHead>
                        <TableHead className="text-right">Avg duration</TableHead>
                        <TableHead>Last used</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {items.map((item, index) => (
                        <TableRow key={toolUsageKey(item)} data-testid="tool-usage-row">
                            <TableCell className="font-mono text-muted-foreground">{index + 1}</TableCell>
                            <TableCell>
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className="font-mono font-semibold">{item.tool_name}</span>
                                    <Link href={historyServerHref(item.server_id, item.server_name)}>
                                        <Badge variant="muted" className="font-normal hover:bg-muted/70">
                                            {item.server_name}
                                        </Badge>
                                    </Link>
                                </div>
                            </TableCell>
                            <TableCell className="text-right font-mono">{item.total_calls.toLocaleString("en-US")}</TableCell>
                            <TableCell className="text-right font-mono">{formatPercent(item.total_calls, totalCalls)}</TableCell>
                            <TableCell className="text-right font-mono">{formatPercent(item.completed_calls, item.total_calls)}</TableCell>
                            <TableCell className="text-right font-mono text-xs">{formatDuration(item.avg_duration_ms)}</TableCell>
                            <TableCell className="text-xs text-muted-foreground">{formatDate(item.last_called_at)}</TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </div>
    );
}
