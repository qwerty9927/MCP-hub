"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Clock, Copy, Check, CheckCircle2, XCircle, Activity, Bot, Calendar, Layers } from "lucide-react";
import { SessionDetailRead } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/common/PageHeader";
import { formatDate } from "@/lib/utils";
import { toast } from "sonner";

interface SessionOverviewProps {
    session: SessionDetailRead;
    onRefresh?: () => void;
    isRefreshing?: boolean;
}

export function SessionOverview({ session, onRefresh, isRefreshing }: SessionOverviewProps) {
    const [copiedId, setCopiedId] = useState(false);

    const handleCopyId = () => {
        navigator.clipboard.writeText(session.id);
        setCopiedId(true);
        setTimeout(() => setCopiedId(false), 2000);
        toast.success("Session ID copied to clipboard");
    };

    const renderStatusBadge = (status: string) => {
        const lower = status.toLowerCase();
        if (lower === "active") {
            return (
                <Badge variant="success" className="gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Active
                </Badge>
            );
        }
        if (lower === "completed") {
            return (
                <Badge variant="secondary" className="gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-muted-foreground" />
                    Completed
                </Badge>
            );
        }
        if (lower === "failed") {
            return (
                <Badge variant="destructive" className="gap-1.5">
                    <XCircle className="h-3.5 w-3.5" />
                    Failed
                </Badge>
            );
        }
        return <Badge variant="outline">{status}</Badge>;
    };

    const displayTitle = session.title || `Session ${session.id.slice(0, 8)}`;

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-2">
                <Button asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
                    <Link href="/sessions">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Sessions
                    </Link>
                </Button>
            </div>

            <PageHeader
                title={displayTitle}
                description={`Session ID: ${session.id}`}
                actions={
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleCopyId}
                            className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                            title="Copy full session ID"
                        >
                            {copiedId ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                            Copy ID
                        </Button>
                        {renderStatusBadge(session.status)}
                        {onRefresh && (
                            <Button variant="outline" size="sm" onClick={onRefresh} disabled={isRefreshing} className="gap-1.5">
                                <Activity className="h-3.5 w-3.5 text-primary" />
                                Refresh
                            </Button>
                        )}
                    </div>
                }
            />

            {/* Overview Metrics Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                        <Activity className="h-3.5 w-3.5 text-primary" />
                        Total Calls
                    </span>
                    <p className="mt-2 text-2xl font-bold font-mono text-foreground">{session.total_tool_calls}</p>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                        Successful
                    </span>
                    <p className="mt-2 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
                        {session.successful_tool_calls}
                    </p>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                        <XCircle className="h-3.5 w-3.5 text-destructive" />
                        Failed
                    </span>
                    <p className="mt-2 text-2xl font-bold font-mono text-destructive">{session.failed_tool_calls}</p>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                        <Bot className="h-3.5 w-3.5 text-muted-foreground" />
                        Status
                    </span>
                    <div className="mt-2">{renderStatusBadge(session.status)}</div>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                        Created
                    </span>
                    <p className="mt-2 text-xs font-mono text-muted-foreground">{formatDate(session.created_at)}</p>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                        Last Activity
                    </span>
                    <p className="mt-2 text-xs font-mono text-muted-foreground">{formatDate(session.last_activity_at)}</p>
                </Card>
            </div>

            {/* Optional Client Metadata */}
            {session.metadata && Object.keys(session.metadata).length > 0 && (
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1 font-medium">
                        <Layers className="h-3.5 w-3.5" />
                        Session Metadata:
                    </span>
                    {Object.entries(session.metadata).map(([key, val]) => (
                        <Badge key={key} variant="outline" className="font-mono text-[11px] py-0.5">
                            {key}: {typeof val === "object" ? JSON.stringify(val) : String(val)}
                        </Badge>
                    ))}
                </div>
            )}
        </div>
    );
}
