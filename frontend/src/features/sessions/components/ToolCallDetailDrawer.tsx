"use client";

import React, { useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToolCallRead } from "@/types";
import { formatDate, formatDuration } from "@/lib/utils";
import { Wrench, Server, Clock, Copy, Check, FileCode2, Terminal, AlertTriangle, Ban } from "lucide-react";
import { toast } from "sonner";
import { ToolCallStatusBadge } from "./ToolCallStatusBadge";

interface ToolCallDetailDrawerProps {
    toolCall: ToolCallRead | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function ToolCallDetailDrawer({ toolCall, open, onOpenChange }: ToolCallDetailDrawerProps) {
    const [copiedId, setCopiedId] = useState(false);
    const [copiedArgs, setCopiedArgs] = useState(false);
    const [copiedResponse, setCopiedResponse] = useState(false);
    const [copiedAll, setCopiedAll] = useState(false);
    const [responseTab, setResponseTab] = useState<"formatted" | "raw">("formatted");

    if (!toolCall) return null;

    const handleCopyId = () => {
        navigator.clipboard.writeText(toolCall.id);
        setCopiedId(true);
        setTimeout(() => setCopiedId(false), 2000);
        toast.success("Tool call ID copied to clipboard");
    };

    const handleCopyArgs = () => {
        navigator.clipboard.writeText(JSON.stringify(toolCall.arguments, null, 2));
        setCopiedArgs(true);
        setTimeout(() => setCopiedArgs(false), 2000);
        toast.success("Arguments copied to clipboard");
    };

    const handleCopyResponse = () => {
        if (!toolCall.response) return;
        navigator.clipboard.writeText(JSON.stringify(toolCall.response, null, 2));
        setCopiedResponse(true);
        setTimeout(() => setCopiedResponse(false), 2000);
        toast.success("Response payload copied to clipboard");
    };

    const handleCopyAll = () => {
        navigator.clipboard.writeText(JSON.stringify(toolCall, null, 2));
        setCopiedAll(true);
        setTimeout(() => setCopiedAll(false), 2000);
        toast.success("Full tool call record copied to clipboard");
    };

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent side="right" className="flex flex-col gap-0 p-0 sm:max-w-xl md:max-w-2xl overflow-hidden">
                {/* Drawer Header */}
                <SheetHeader className="p-6 border-b border-border bg-card/60 space-y-2">
                    <div className="flex items-center gap-2">
                        <ToolCallStatusBadge status={toolCall.status} />
                        <Badge variant="outline" className="gap-1 text-xs text-muted-foreground">
                            <Server className="h-3 w-3 text-primary" />
                            {toolCall.server_name}
                        </Badge>
                    </div>

                    <SheetTitle className="text-xl flex items-center gap-2">
                        <Wrench className="h-5 w-5 text-primary shrink-0" />
                        <span className="truncate">{toolCall.tool_name}</span>
                    </SheetTitle>

                    <SheetDescription asChild>
                        <div className="flex items-center justify-between text-xs font-mono text-muted-foreground">
                            <span className="truncate max-w-[280px] sm:max-w-sm">Call ID: {toolCall.id}</span>
                            <div className="flex items-center gap-1.5 shrink-0">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={handleCopyId}
                                    className="h-6 px-2 text-[11px] text-muted-foreground hover:text-foreground"
                                >
                                    {copiedId ? <Check className="h-3 w-3 text-emerald-500 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                                    Copy ID
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={handleCopyAll}
                                    className="h-6 px-2 text-[11px] text-muted-foreground hover:text-foreground"
                                >
                                    {copiedAll ? <Check className="h-3 w-3 text-emerald-500 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                                    Copy JSON
                                </Button>
                            </div>
                        </div>
                    </SheetDescription>
                </SheetHeader>

                {/* Drawer Scrollable Body */}
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                    {/* Execution Metrics Summary */}
                    <div className="grid grid-cols-3 gap-3">
                        <div className="rounded-lg border border-border bg-muted/30 p-3">
                            <span className="text-[11px] text-muted-foreground font-medium flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                Duration
                            </span>
                            <p className="mt-1 text-sm font-mono font-bold text-foreground">{formatDuration(toolCall.duration_ms)}</p>
                        </div>

                        <div className="rounded-lg border border-border bg-muted/30 p-3">
                            <span className="text-[11px] text-muted-foreground font-medium flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                Started At
                            </span>
                            <p className="mt-1 text-xs font-mono text-muted-foreground truncate">{formatDate(toolCall.started_at)}</p>
                        </div>

                        <div className="rounded-lg border border-border bg-muted/30 p-3">
                            <span className="text-[11px] text-muted-foreground font-medium flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                Completed At
                            </span>
                            <p className="mt-1 text-xs font-mono text-muted-foreground truncate">{formatDate(toolCall.completed_at)}</p>
                        </div>
                    </div>

                    {/* Error Banner if Execution Failed */}
                    {toolCall.status === "failed" && (
                        <Card className="border-destructive/30 bg-destructive/10">
                            <CardHeader className="p-4 pb-2">
                                <CardTitle className="text-sm font-semibold text-destructive flex items-center gap-2">
                                    <AlertTriangle className="h-4 w-4" />
                                    Execution Error
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="p-4 pt-0">
                                <p className="font-mono text-xs text-destructive dark:text-red-300 whitespace-pre-wrap break-all">
                                    {toolCall.error_summary || "Tool call reported an execution failure without error summary."}
                                </p>
                            </CardContent>
                        </Card>
                    )}

                    {/* Rejection Banner: the hub refused the call before contacting the downstream Server */}
                    {toolCall.status === "rejected" && (
                        <Card className="border-orange-500/30 bg-orange-500/10">
                            <CardHeader className="p-4 pb-2">
                                <CardTitle className="text-sm font-semibold text-orange-700 dark:text-orange-400 flex items-center gap-2">
                                    <Ban className="h-4 w-4" />
                                    Execution Rejected
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="p-4 pt-0">
                                <p className="font-mono text-xs text-orange-700 dark:text-orange-300 whitespace-pre-wrap break-all">
                                    {toolCall.error_summary || "The hub rejected this tool call before it reached the downstream server."}
                                </p>
                            </CardContent>
                        </Card>
                    )}

                    {/* Invocation Arguments */}
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between p-4 pb-2">
                            <div className="space-y-0.5">
                                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                                    <Terminal className="h-4 w-4 text-primary" />
                                    Input Arguments
                                </CardTitle>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={handleCopyArgs}
                                className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                            >
                                {copiedArgs ? <Check className="h-3 w-3 text-emerald-500 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                                Copy
                            </Button>
                        </CardHeader>
                        <CardContent className="p-4 pt-2">
                            <pre className="rounded-lg bg-muted/60 p-3.5 font-mono text-xs overflow-x-auto border border-border max-h-[300px]">
                                {JSON.stringify(toolCall.arguments, null, 2)}
                            </pre>
                        </CardContent>
                    </Card>

                    {/* Output Result */}
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between p-4 pb-2">
                            <div className="space-y-0.5">
                                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                                    <FileCode2 className="h-4 w-4 text-primary" />
                                    Output Result
                                </CardTitle>
                            </div>
                            {toolCall.response && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={handleCopyResponse}
                                    className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                                >
                                    {copiedResponse ? (
                                        <Check className="h-3 w-3 text-emerald-500 mr-1" />
                                    ) : (
                                        <Copy className="h-3 w-3 mr-1" />
                                    )}
                                    Copy
                                </Button>
                            )}
                        </CardHeader>
                        <CardContent className="p-4 pt-2">
                            {!toolCall.response ? (
                                <div className="rounded-lg border border-dashed border-border p-6 text-center text-muted-foreground">
                                    <Terminal className="h-6 w-6 opacity-40 mx-auto mb-2" />
                                    <p className="text-xs font-medium">No response payload recorded</p>
                                </div>
                            ) : (
                                <Tabs value={responseTab} onValueChange={(v: any) => setResponseTab(v)}>
                                    <TabsList className="h-7 max-w-[200px] grid grid-cols-2 mb-3">
                                        <TabsTrigger value="formatted" className="text-xs h-6">
                                            Formatted
                                        </TabsTrigger>
                                        <TabsTrigger value="raw" className="text-xs h-6">
                                            Raw JSON
                                        </TabsTrigger>
                                    </TabsList>

                                    <TabsContent value="formatted" className="space-y-2 mt-0">
                                        {toolCall.response.content && Array.isArray(toolCall.response.content) ? (
                                            toolCall.response.content.map((item: any, idx: number) => (
                                                <div
                                                    key={idx}
                                                    className="rounded-lg border border-border bg-muted/40 p-3 text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all max-h-60"
                                                >
                                                    {item.text || JSON.stringify(item, null, 2)}
                                                </div>
                                            ))
                                        ) : (
                                            <pre className="rounded-lg bg-muted/60 p-3.5 font-mono text-xs overflow-x-auto border border-border max-h-[300px]">
                                                {JSON.stringify(toolCall.response, null, 2)}
                                            </pre>
                                        )}
                                    </TabsContent>

                                    <TabsContent value="raw" className="mt-0">
                                        <pre className="rounded-lg bg-muted/60 p-3.5 font-mono text-xs overflow-x-auto border border-border max-h-[300px]">
                                            {JSON.stringify(toolCall.response, null, 2)}
                                        </pre>
                                    </TabsContent>
                                </Tabs>
                            )}
                        </CardContent>
                    </Card>
                </div>
            </SheetContent>
        </Sheet>
    );
}
