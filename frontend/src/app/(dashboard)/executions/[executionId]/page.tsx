"use client";

import React, { use, useState } from "react";
import Link from "next/link";
import { historyServerHref } from "@/lib/server-links";
import { ArrowLeft, Clock, Server, Wrench, Play, XCircle, Copy, Check, FileCode2, Terminal } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ContentBlock, JsonTabs, JsonViewer } from "@/components/common/JsonViewer";
import { Skeleton } from "@/components/ui/skeleton";
import { CardGridSkeleton } from "@/components/common/CardGridSkeleton";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { useExecution } from "@/features/executions/hooks/use-executions";
import { ToolCallStatusBadge } from "@/components/common/ToolCallStatusBadge";
import { executionStatus, formatDate, formatDuration } from "@/lib/utils";
import { toast } from "sonner";

interface ExecutionDetailPageProps {
    params: Promise<{ executionId: string }>;
}

export default function ExecutionDetailPage({ params }: ExecutionDetailPageProps) {
    const { executionId } = use(params);
    const [copiedJson, setCopiedJson] = useState(false);
    const [copiedArgs, setCopiedArgs] = useState(false);
    const [copiedResponse, setCopiedResponse] = useState(false);

    const { data: execution, isLoading, isError, error, refetch } = useExecution(executionId);

    const handleCopyJson = () => {
        if (!execution) return;
        navigator.clipboard.writeText(JSON.stringify(execution, null, 2));
        setCopiedJson(true);
        setTimeout(() => setCopiedJson(false), 2000);
        toast.success("Full execution record copied to clipboard");
    };

    const handleCopyArgs = () => {
        if (!execution) return;
        navigator.clipboard.writeText(JSON.stringify(execution.arguments, null, 2));
        setCopiedArgs(true);
        setTimeout(() => setCopiedArgs(false), 2000);
        toast.success("Invocation arguments copied to clipboard");
    };

    const handleCopyResponse = () => {
        if (!execution?.response) return;
        navigator.clipboard.writeText(JSON.stringify(execution.response, null, 2));
        setCopiedResponse(true);
        setTimeout(() => setCopiedResponse(false), 2000);
        toast.success("Response payload copied to clipboard");
    };

    if (isLoading) {
        return (
            <div className="space-y-6">
                <div className="flex items-center gap-2">
                    <Skeleton className="h-8 w-36 rounded-md" />
                </div>
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between pb-6 border-b border-border">
                    <div className="space-y-2">
                        <Skeleton className="h-8 w-48" />
                        <Skeleton className="h-4 w-96 max-w-full" />
                    </div>
                    <Skeleton className="h-9 w-28 rounded-md" />
                </div>
                <CardGridSkeleton count={4} />
                <div className="rounded-xl border border-border bg-card p-6 space-y-4">
                    <Skeleton className="h-6 w-36" />
                    <Skeleton className="h-32 w-full rounded-md" />
                </div>
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
                    message={(error as any)?.message || "Could not locate execution record with the given ID."}
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
                        <Button variant="outline" size="sm" onClick={handleCopyJson} className="gap-1.5">
                            {copiedJson ? <Check className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
                            Copy JSON
                        </Button>
                        <Button asChild size="sm" className="gap-1.5">
                            <Link href={`/playground?server=${execution.server_id}&tool=${encodeURIComponent(execution.tool_name)}`}>
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
                        <ToolCallStatusBadge status={executionStatus(execution)} className="gap-1.5" />
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
                            href={historyServerHref(execution.server_id, execution.server_name)}
                            className="text-sm font-medium hover:underline text-foreground truncate"
                        >
                            {execution.server_name}
                        </Link>
                    </div>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">Executed At</span>
                    <p className="mt-2 text-xs font-mono text-muted-foreground">{formatDate(execution.executed_at)}</p>
                </Card>
            </div>

            {execution.is_error && (execution.error_message || execution.response?.content) && (
                <Card className="border-destructive/30 bg-destructive/10">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-semibold text-destructive flex items-center gap-2">
                            <XCircle className="h-4 w-4" />
                            Error Details
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="font-mono text-xs text-destructive dark:text-red-300 whitespace-pre-wrap break-all">
                            {execution.error_message ||
                                execution.response?.content
                                    ?.filter((c: any) => c.type === "text" && c.text)
                                    .map((c: any) => c.text)
                                    .join("\n") ||
                                "Tool invocation reported an error"}
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* Dual Panels: Invocation Arguments and Response Output */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Left: Invocation Arguments Card */}
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-3">
                        <div className="space-y-1">
                            <CardTitle className="text-base flex items-center gap-2">
                                <Wrench className="h-4 w-4 text-primary" />
                                Invocation Arguments
                            </CardTitle>
                            <CardDescription>Key-value payload passed to tool</CardDescription>
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleCopyArgs}
                            className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                        >
                            {copiedArgs ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                            Copy
                        </Button>
                    </CardHeader>
                    <CardContent>
                        <JsonTabs
                            formatted={<JsonViewer value={execution.arguments} className="max-h-[500px]" />}
                            raw={execution.arguments}
                            rawClassName="max-h-[500px]"
                        />
                    </CardContent>
                </Card>

                {/* Right: Response Output Card */}
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-3">
                        <div className="space-y-1">
                            <CardTitle className="text-base flex items-center gap-2">
                                <FileCode2 className="h-4 w-4 text-primary" />
                                Tool Output Response
                            </CardTitle>
                            <CardDescription>Payload returned by downstream MCP server</CardDescription>
                        </div>
                        {execution.response && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={handleCopyResponse}
                                className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                            >
                                {copiedResponse ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                                Copy
                            </Button>
                        )}
                    </CardHeader>
                    <CardContent>
                        {!execution.response ? (
                            <div className="rounded-lg border border-dashed border-border p-8 text-center text-muted-foreground">
                                <Terminal className="h-8 w-8 opacity-40 mx-auto mb-2" />
                                <p className="text-sm font-medium">No response payload recorded</p>
                                <p className="text-xs text-muted-foreground mt-1">
                                    This execution entry does not contain a saved downstream response.
                                </p>
                            </div>
                        ) : (
                            <JsonTabs
                                raw={execution.response}
                                rawClassName="max-h-[500px]"
                                formatted={
                                    <div className="space-y-3">
                                        {execution.response.content && execution.response.content.length > 0 ? (
                                            <div className="space-y-2">
                                                <span className="text-xs font-medium text-muted-foreground">
                                                    Content Blocks ({execution.response.content.length}
                                                    ):
                                                </span>
                                                {execution.response.content.map((item, idx) => (
                                                    <ContentBlock key={idx} item={item} className="max-h-[500px]" />
                                                ))}
                                            </div>
                                        ) : (
                                            <p className="text-xs text-muted-foreground italic">No text content blocks in response.</p>
                                        )}

                                        {execution.response.structured_content && (
                                            <div className="space-y-1.5 pt-2">
                                                <span className="text-xs font-medium text-muted-foreground">Structured Output:</span>
                                                <JsonViewer value={execution.response.structured_content} className="max-h-80" />
                                            </div>
                                        )}
                                    </div>
                                }
                            />
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
