"use client";

import React, { use } from "react";
import Link from "next/link";
import {
    ArrowLeft,
    Clock,
    Server,
    Wrench,
    Play,
    CheckCircle2,
    XCircle,
    Copy,
    Check,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { useExecution } from "@/features/executions/hooks/use-executions";
import { formatDate, formatDuration } from "@/lib/utils";
import { toast } from "sonner";

interface ExecutionDetailPageProps {
    params: Promise<{ executionId: string }>;
}

export default function ExecutionDetailPage({ params }: ExecutionDetailPageProps) {
    const { executionId } = use(params);
    const [copied, setCopied] = React.useState(false);

    const { data: execution, isLoading, isError, error, refetch } = useExecution(executionId);

    const handleCopy = () => {
        if (!execution) return;
        navigator.clipboard.writeText(JSON.stringify(execution, null, 2));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        toast.success("Execution record copied to clipboard");
    };

    if (isLoading) {
        return (
            <div className="space-y-6">
                <Skeleton className="h-8 w-48" />
                <Skeleton className="h-28 w-full" />
                <Skeleton className="h-64 w-full" />
            </div>
        );
    }

    if (isError || !execution) {
        return (
            <div className="space-y-6">
                <Button asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
                    <Link href="/executions">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Execution History
                    </Link>
                </Button>
                <ErrorAlert
                    title="Execution Record Not Found"
                    message={
                        (error as any)?.message ||
                        "Could not locate execution record with the given ID."
                    }
                    onRetry={() => refetch()}
                />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-2">
                <Button asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
                    <Link href="/executions">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Execution History
                    </Link>
                </Button>
            </div>

            <PageHeader
                title={`Execution: ${execution.tool_name}`}
                description={`Audit record for invocation ID ${execution.id}`}
                actions={
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleCopy}
                            className="gap-1.5"
                        >
                            {copied ? (
                                <Check className="h-4 w-4 text-emerald-500" />
                            ) : (
                                <Copy className="h-4 w-4" />
                            )}
                            Copy JSON
                        </Button>
                        <Button asChild size="sm" className="gap-1.5">
                            <Link
                                href={`/playground?server=${execution.server_id}&tool=${encodeURIComponent(
                                    execution.tool_name
                                )}`}
                            >
                                <Play className="h-4 w-4" />
                                Re-run in Playground
                            </Link>
                        </Button>
                    </div>
                }
            />

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">Status</span>
                    <div className="mt-2">
                        {execution.is_error ? (
                            <Badge variant="destructive" className="gap-1.5">
                                <XCircle className="h-3.5 w-3.5" />
                                Failed
                            </Badge>
                        ) : (
                            <Badge variant="success" className="gap-1.5">
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                Success
                            </Badge>
                        )}
                    </div>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">Duration</span>
                    <p className="mt-2 text-sm font-mono font-semibold flex items-center gap-1.5 text-foreground">
                        <Clock className="h-4 w-4 text-muted-foreground" />
                        {formatDuration(execution.duration_ms)}
                    </p>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">Target Server</span>
                    <div className="mt-2 flex items-center gap-1.5">
                        <Server className="h-4 w-4 text-primary" />
                        <Link
                            href={`/servers/${execution.server_id}`}
                            className="text-sm font-medium hover:underline text-foreground truncate"
                        >
                            {execution.server_name}
                        </Link>
                    </div>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">Executed At</span>
                    <p className="mt-2 text-xs font-mono text-muted-foreground">
                        {formatDate(execution.executed_at)}
                    </p>
                </Card>
            </div>

            {execution.is_error && execution.error_message && (
                <Card className="border-destructive/30 bg-destructive/10">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-semibold text-destructive flex items-center gap-2">
                            <XCircle className="h-4 w-4" />
                            Error Message
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="font-mono text-xs text-destructive dark:text-red-300">
                            {execution.error_message}
                        </p>
                    </CardContent>
                </Card>
            )}

            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        <Wrench className="h-4 w-4 text-primary" />
                        Invocation Arguments
                    </CardTitle>
                    <CardDescription>
                        Key-value payload passed to the MCP tool invocation.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <pre className="rounded-lg bg-muted/60 p-4 font-mono text-xs overflow-x-auto border border-border">
                        {JSON.stringify(execution.arguments, null, 2)}
                    </pre>
                </CardContent>
            </Card>
        </div>
    );
}
