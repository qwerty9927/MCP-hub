"use client";

import React from "react";
import Link from "next/link";
import { ToolRead } from "@/types";
import { HealthBadge } from "@/components/common/HealthBadge";
import { Button } from "@/components/ui/button";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Play, ExternalLink } from "lucide-react";
import { formatDate } from "@/lib/utils";

interface ToolListTableProps {
    tools: ToolRead[];
}

export function ToolListTable({ tools }: ToolListTableProps) {
    return (
        <div className="rounded-md border border-border bg-card">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>Tool Name</TableHead>
                        <TableHead>Server</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Parameters</TableHead>
                        <TableHead>Last Discovered</TableHead>
                        <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {tools.map((tool) => {
                        const properties = tool.input_schema?.properties || {};
                        const requiredCount = tool.input_schema?.required?.length || 0;
                        const propKeys = Object.keys(properties);

                        return (
                            <TableRow key={tool.id} className="group">
                                <TableCell className="font-medium">
                                    <div className="flex flex-col">
                                        <Link
                                            href={`/tools/${encodeURIComponent(tool.id)}`}
                                            className="font-mono font-semibold text-foreground hover:text-primary transition-colors flex items-center gap-1.5"
                                        >
                                            {tool.name}
                                            <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                                        </Link>
                                        <span className="text-[11px] font-mono text-muted-foreground">
                                            ID: {tool.id}
                                        </span>
                                    </div>
                                </TableCell>

                                <TableCell>
                                    <Link
                                        href={`/servers/${tool.server_id}`}
                                        className="inline-flex items-center text-xs font-medium text-foreground hover:underline"
                                    >
                                        {tool.server_name}
                                    </Link>
                                </TableCell>

                                <TableCell className="text-xs text-muted-foreground max-w-sm">
                                    <p className="line-clamp-2">
                                        {tool.description || "No description"}
                                    </p>
                                </TableCell>

                                <TableCell>
                                    <HealthBadge status={tool.availability_status} />
                                </TableCell>

                                <TableCell>
                                    <span className="inline-flex items-center text-xs font-mono bg-muted/70 px-2 py-0.5 rounded">
                                        {propKeys.length} schema params ({requiredCount} req)
                                    </span>
                                </TableCell>

                                <TableCell className="text-xs text-muted-foreground">
                                    {formatDate(tool.last_discovered_at)}
                                </TableCell>

                                <TableCell className="text-right">
                                    <Button asChild size="sm" variant="outline" className="gap-1.5">
                                        <Link
                                            href={`/playground?server=${tool.server_id}&tool=${encodeURIComponent(
                                                tool.name
                                            )}`}
                                        >
                                            <Play className="h-3.5 w-3.5 text-primary" />
                                            Test
                                        </Link>
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
