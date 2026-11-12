"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Copy, Check, ExternalLink, Activity, CheckCircle2, XCircle } from "lucide-react";
import { SessionRead } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate } from "@/lib/utils";
import { toast } from "sonner";

interface SessionListTableProps {
    sessions: SessionRead[];
}

export function SessionListTable({ sessions }: SessionListTableProps) {
    const [copiedId, setCopiedId] = useState<string | null>(null);

    const handleCopyId = (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        e.preventDefault();
        navigator.clipboard.writeText(id);
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 2000);
        toast.success("Session ID copied to clipboard");
    };

    const renderStatusBadge = (status: string) => {
        const lower = status.toLowerCase();
        if (lower === "active") {
            return (
                <Badge variant="success" className="gap-1.5 text-xs">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Active
                </Badge>
            );
        }
        if (lower === "completed") {
            return (
                <Badge variant="secondary" className="gap-1.5 text-xs">
                    <CheckCircle2 className="h-3 w-3 text-muted-foreground" />
                    Completed
                </Badge>
            );
        }
        if (lower === "failed") {
            return (
                <Badge variant="destructive" className="gap-1.5 text-xs">
                    <XCircle className="h-3 w-3" />
                    Failed
                </Badge>
            );
        }
        return <Badge variant="outline">{status}</Badge>;
    };

    return (
        <div className="rounded-md border border-border bg-card">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead className="w-[180px]">Session ID</TableHead>
                        <TableHead>Title / Identifier</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-center">Total Tool Calls</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead>Last Activity</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {sessions.map((session) => {
                        const isCopied = copiedId === session.id;
                        const displayTitle = session.title || `Session ${session.id.slice(0, 8)}`;

                        return (
                            <TableRow key={session.id} className="group hover:bg-muted/40 transition-colors">
                                <TableCell className="font-mono text-xs">
                                    <div className="flex items-center gap-1.5">
                                        <span className="text-foreground font-semibold truncate max-w-[120px]" title={session.id}>
                                            {session.id.slice(0, 8)}...
                                        </span>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            onClick={(e) => handleCopyId(session.id, e)}
                                            className="h-6 w-6 text-muted-foreground hover:text-foreground opacity-60 group-hover:opacity-100"
                                            title="Copy full session ID"
                                        >
                                            {isCopied ? (
                                                <Check className="h-3.5 w-3.5 text-emerald-500" />
                                            ) : (
                                                <Copy className="h-3.5 w-3.5" />
                                            )}
                                        </Button>
                                    </div>
                                </TableCell>

                                <TableCell>
                                    <Link
                                        href={`/sessions/${session.id}`}
                                        className="font-semibold text-foreground hover:text-primary transition-colors flex items-center gap-1.5"
                                    >
                                        <span className="truncate max-w-xs">{displayTitle}</span>
                                        <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                                    </Link>
                                </TableCell>

                                <TableCell>{renderStatusBadge(session.status)}</TableCell>

                                <TableCell className="text-center">
                                    <span className="inline-flex items-center justify-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-semibold text-foreground">
                                        {session.total_tool_calls}
                                    </span>
                                </TableCell>

                                <TableCell className="text-xs text-muted-foreground">{formatDate(session.created_at)}</TableCell>

                                <TableCell className="text-xs text-muted-foreground">{formatDate(session.last_activity_at)}</TableCell>

                                <TableCell className="text-right">
                                    <Button asChild variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
                                        <Link href={`/sessions/${session.id}`}>
                                            <Activity className="h-3.5 w-3.5 text-primary" />
                                            View Session
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
