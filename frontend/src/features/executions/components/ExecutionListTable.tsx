"use client";

import React from "react";
import Link from "next/link";
import { ExecutionRecord } from "@/types";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Clock, ExternalLink } from "lucide-react";
import { ToolCallStatusBadge } from "@/components/common/ToolCallStatusBadge";
import { executionStatus, formatDate, formatDuration } from "@/lib/utils";

interface ExecutionListTableProps {
    executions: ExecutionRecord[];
}

export function ExecutionListTable({ executions }: ExecutionListTableProps) {
    return (
        <div className="rounded-md border border-border bg-card">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>Status</TableHead>
                        <TableHead>Tool</TableHead>
                        <TableHead>Server</TableHead>
                        <TableHead>Arguments</TableHead>
                        <TableHead>Duration</TableHead>
                        <TableHead>Executed At</TableHead>
                        <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {executions.map((exec) => {
                        const argsString = JSON.stringify(exec.arguments);

                        return (
                            <TableRow key={exec.id} className="group">
                                <TableCell>
                                    <ToolCallStatusBadge status={executionStatus(exec)} className="font-medium" />
                                </TableCell>

                                <TableCell className="font-mono font-semibold">
                                    <Link
                                        href={`/executions/${exec.id}`}
                                        className="hover:text-primary transition-colors flex items-center gap-1.5"
                                    >
                                        {exec.tool_name}
                                        <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                                    </Link>
                                </TableCell>

                                <TableCell>
                                    <Link href={`/servers/${exec.server_id}`} className="text-xs hover:underline text-muted-foreground">
                                        {exec.server_name}
                                    </Link>
                                </TableCell>

                                <TableCell className="max-w-xs text-xs font-mono text-muted-foreground truncate">
                                    {argsString === "{}" ? "-" : argsString}
                                </TableCell>

                                <TableCell className="text-xs font-mono">
                                    <span className="flex items-center gap-1">
                                        <Clock className="h-3 w-3 text-muted-foreground" />
                                        {formatDuration(exec.duration_ms)}
                                    </span>
                                </TableCell>

                                <TableCell className="text-xs text-muted-foreground">{formatDate(exec.executed_at)}</TableCell>

                                <TableCell className="text-right">
                                    <Button asChild size="sm" variant="outline" className="h-8 text-xs">
                                        <Link href={`/executions/${exec.id}`}>Details</Link>
                                    </Button>
                                </TableCell>
                            </TableRow>
                        );
                    })}
                </TableBody>
            </Table>
        </div>
    );
}
