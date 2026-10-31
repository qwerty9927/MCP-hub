"use client";

import React, { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
    Play,
    Copy,
    Check,
    AlertTriangle,
    Code,
    FileText,
    Clock,
    History,
    CheckCircle2,
    XCircle,
    Loader2,
    Server as ServerIcon,
    Wrench,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { SchemaForm } from "./SchemaForm";
import { useServers } from "@/features/servers/hooks/use-servers";
import { useTools, useExecuteTool } from "@/features/tools/hooks/use-tools";
import { ToolExecuteResponse, ToolRead } from "@/types";
import { formatDuration } from "@/lib/utils";

export function ToolPlayground() {
    const searchParams = useSearchParams();
    const router = useRouter();

    const initialServerId = searchParams.get("server") || "";
    const initialToolName = searchParams.get("tool") || "";

    const [selectedServerId, setSelectedServerId] = useState<string>(initialServerId);
    const [selectedToolName, setSelectedToolName] = useState<string>(initialToolName);

    // Form values state
    const [formValues, setFormValues] = useState<Record<string, any>>({});
    const [jsonText, setJsonText] = useState<string>("{}");
    const [jsonError, setJsonError] = useState<string | null>(null);
    const [inputMode, setInputMode] = useState<"visual" | "json">("visual");

    // Safety confirmation dialog state
    const [confirmOpen, setConfirmOpen] = useState(false);
    const [copied, setCopied] = useState(false);

    // Execution result state
    const [result, setResult] = useState<ToolExecuteResponse | null>(null);

    // Fetch servers
    const { data: serversData } = useServers({ page: 1, page_size: 100 });
    const servers = serversData?.items || [];

    // Fetch tools for selected server
    const { data: toolsData, isLoading: toolsLoading } = useTools({
        server_id: selectedServerId || undefined,
        page: 1,
        page_size: 100,
    });
    const tools = toolsData?.items || [];

    // Find currently active tool
    const currentTool: ToolRead | undefined = tools.find((t) => t.name === selectedToolName);

    const executeMutation = useExecuteTool();

    // Sync initial query params
    useEffect(() => {
        if (initialServerId && initialServerId !== selectedServerId) {
            setSelectedServerId(initialServerId);
        }
    }, [initialServerId]);

    useEffect(() => {
        if (initialToolName && initialToolName !== selectedToolName) {
            setSelectedToolName(initialToolName);
        }
    }, [initialToolName]);

    // Reset form values when tool changes
    useEffect(() => {
        if (currentTool) {
            // Build default values from schema
            const defaults: Record<string, any> = {};
            const props = currentTool.input_schema?.properties || {};
            for (const [k, v] of Object.entries<any>(props)) {
                if (v.default !== undefined) {
                    defaults[k] = v.default;
                }
            }
            setFormValues(defaults);
            setJsonText(JSON.stringify(defaults, null, 2));
            setResult(null);
        }
    }, [currentTool?.id]);

    const handleServerChange = (serverId: string) => {
        setSelectedServerId(serverId);
        setSelectedToolName("");
        setResult(null);
        router.replace(`/playground?server=${serverId}`);
    };

    const handleToolChange = (toolName: string) => {
        setSelectedToolName(toolName);
        setResult(null);
        router.replace(
            `/playground?server=${selectedServerId}&tool=${encodeURIComponent(toolName)}`
        );
    };

    const handleJsonChange = (text: string) => {
        setJsonText(text);
        try {
            const parsed = JSON.parse(text);
            setFormValues(parsed);
            setJsonError(null);
        } catch (err: any) {
            setJsonError(err.message || "Invalid JSON syntax");
        }
    };

    const handleFormChange = (vals: Record<string, any>) => {
        setFormValues(vals);
        setJsonText(JSON.stringify(vals, null, 2));
        setJsonError(null);
    };

    const isPotentiallyDestructive = (name: string) => {
        const lower = name.toLowerCase();
        return (
            lower.includes("delete") ||
            lower.includes("remove") ||
            lower.includes("drop") ||
            lower.includes("destroy") ||
            lower.includes("write") ||
            lower.includes("exec")
        );
    };

    const triggerExecution = () => {
        if (!currentTool) return;

        let args = formValues;
        if (inputMode === "json") {
            try {
                args = JSON.parse(jsonText);
            } catch {
                toast.error("Please fix invalid JSON before running");
                return;
            }
        }

        if (isPotentiallyDestructive(currentTool.name)) {
            setConfirmOpen(true);
            return;
        }

        runTool(args);
    };

    const runTool = async (args: Record<string, any>) => {
        if (!currentTool) return;
        try {
            const res = await executeMutation.mutateAsync({
                serverId: currentTool.server_id,
                toolName: currentTool.name,
                payload: { arguments: args },
            });
            setResult(res);
        } catch {
            // Mutation handles error notification
        }
    };

    const handleCopyResult = () => {
        if (!result) return;
        navigator.clipboard.writeText(JSON.stringify(result, null, 2));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        toast.success("Result copied to clipboard");
    };

    return (
        <div className="space-y-6">
            {/* Target Selector Bar */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                        <ServerIcon className="h-4 w-4 text-primary" />
                        Target Server & Tool Selection
                    </CardTitle>
                    <CardDescription>
                        Select an active MCP server and discovered tool to test invocations.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                            <label className="text-xs font-medium text-muted-foreground">
                                MCP Server
                            </label>
                            <Select value={selectedServerId} onValueChange={handleServerChange}>
                                <SelectTrigger className="h-9">
                                    <SelectValue placeholder="Select an MCP Server..." />
                                </SelectTrigger>
                                <SelectContent>
                                    {servers.map((s) => (
                                        <SelectItem key={s.id} value={s.id}>
                                            {s.name} ({s.transport})
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-medium text-muted-foreground">
                                MCP Tool
                            </label>
                            <Select
                                value={selectedToolName}
                                onValueChange={handleToolChange}
                                disabled={!selectedServerId || toolsLoading}
                            >
                                <SelectTrigger className="h-9">
                                    <SelectValue
                                        placeholder={
                                            !selectedServerId
                                                ? "Select server first..."
                                                : toolsLoading
                                                  ? "Loading tools..."
                                                  : tools.length === 0
                                                    ? "No tools found"
                                                    : "Select tool..."
                                        }
                                    />
                                </SelectTrigger>
                                <SelectContent>
                                    {tools.map((t) => (
                                        <SelectItem key={t.id} value={t.name}>
                                            {t.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Main Execution Grid */}
            {currentTool ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                    {/* Left Column: Input Arguments */}
                    <div className="space-y-4">
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <CardTitle className="text-lg font-mono flex items-center gap-2">
                                            <Wrench className="h-4 w-4 text-primary" />
                                            {currentTool.name}
                                        </CardTitle>
                                        {currentTool.description && (
                                            <CardDescription className="mt-1">
                                                {currentTool.description}
                                            </CardDescription>
                                        )}
                                    </div>

                                    <Tabs
                                        value={inputMode}
                                        onValueChange={(val: any) => setInputMode(val)}
                                    >
                                        <TabsList className="h-8">
                                            <TabsTrigger
                                                value="visual"
                                                className="h-7 text-xs gap-1"
                                            >
                                                <FileText className="h-3 w-3" />
                                                Form
                                            </TabsTrigger>
                                            <TabsTrigger value="json" className="h-7 text-xs gap-1">
                                                <Code className="h-3 w-3" />
                                                JSON
                                            </TabsTrigger>
                                        </TabsList>
                                    </Tabs>
                                </div>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {inputMode === "visual" ? (
                                    <SchemaForm
                                        schema={currentTool.input_schema}
                                        values={formValues}
                                        onChange={handleFormChange}
                                        disabled={executeMutation.isPending}
                                    />
                                ) : (
                                    <div className="space-y-2">
                                        <Textarea
                                            value={jsonText}
                                            onChange={(e) => handleJsonChange(e.target.value)}
                                            rows={12}
                                            className="font-mono text-xs"
                                            disabled={executeMutation.isPending}
                                            placeholder="{}"
                                        />
                                        {jsonError && (
                                            <p className="text-xs text-destructive">{jsonError}</p>
                                        )}
                                    </div>
                                )}

                                <div className="flex items-center justify-between pt-2 border-t border-border">
                                    <div className="text-xs text-muted-foreground">
                                        All executions route safely through FastAPI backend.
                                    </div>
                                    <Button
                                        onClick={triggerExecution}
                                        disabled={executeMutation.isPending || Boolean(jsonError)}
                                        className="gap-2"
                                    >
                                        {executeMutation.isPending ? (
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                        ) : (
                                            <Play className="h-4 w-4 fill-current" />
                                        )}
                                        Execute Tool
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Right Column: Execution Output */}
                    <div className="space-y-4">
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center justify-between">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <span>Response Output</span>
                                        {result && (
                                            <div className="flex items-center gap-2">
                                                {result.is_error ? (
                                                    <span className="inline-flex items-center gap-1 rounded-md bg-destructive/15 px-2 py-0.5 text-xs font-semibold text-destructive">
                                                        <XCircle className="h-3 w-3" />
                                                        Failed
                                                    </span>
                                                ) : (
                                                    <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/15 px-2 py-0.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                                                        <CheckCircle2 className="h-3 w-3" />
                                                        Success
                                                    </span>
                                                )}
                                                <span className="inline-flex items-center gap-1 text-xs font-mono text-muted-foreground">
                                                    <Clock className="h-3 w-3" />
                                                    {formatDuration(result.duration_ms)}
                                                </span>
                                            </div>
                                        )}
                                    </CardTitle>

                                    {result && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={handleCopyResult}
                                            className="h-8 gap-1.5 text-xs"
                                        >
                                            {copied ? (
                                                <Check className="h-3.5 w-3.5 text-emerald-500" />
                                            ) : (
                                                <Copy className="h-3.5 w-3.5" />
                                            )}
                                            Copy
                                        </Button>
                                    )}
                                </div>
                            </CardHeader>
                            <CardContent>
                                {executeMutation.isPending ? (
                                    <div className="flex flex-col items-center justify-center p-12 text-center text-muted-foreground">
                                        <Loader2 className="h-8 w-8 animate-spin text-primary mb-3" />
                                        <p className="text-sm font-medium">Invoking MCP tool...</p>
                                        <p className="text-xs text-muted-foreground mt-1">
                                            Executing on backend through transport session
                                        </p>
                                    </div>
                                ) : result ? (
                                    <div className="space-y-4">
                                        {/* Textual content items */}
                                        {result.content && result.content.length > 0 && (
                                            <div className="space-y-2">
                                                <span className="text-xs font-medium text-muted-foreground">
                                                    Content Blocks:
                                                </span>
                                                {result.content.map((item, idx) => (
                                                    <div
                                                        key={idx}
                                                        className="rounded-lg border border-border bg-muted/40 p-3 text-sm font-mono overflow-x-auto whitespace-pre-wrap break-all"
                                                    >
                                                        {item.text || JSON.stringify(item, null, 2)}
                                                    </div>
                                                ))}
                                            </div>
                                        )}

                                        {/* Structured Content if present */}
                                        {result.structured_content && (
                                            <div className="space-y-2">
                                                <span className="text-xs font-medium text-muted-foreground">
                                                    Structured Result:
                                                </span>
                                                <pre className="rounded-lg border border-border bg-muted/40 p-3 text-xs font-mono overflow-x-auto">
                                                    {JSON.stringify(
                                                        result.structured_content,
                                                        null,
                                                        2
                                                    )}
                                                </pre>
                                            </div>
                                        )}

                                        {/* Execution Audit Link */}
                                        <div className="flex items-center justify-between pt-2 border-t border-border text-xs text-muted-foreground">
                                            <span>Execution ID: {result.execution_id}</span>
                                            <Button
                                                asChild
                                                variant="link"
                                                size="sm"
                                                className="h-auto p-0 text-xs"
                                            >
                                                <Link href={`/executions/${result.execution_id}`}>
                                                    <History className="mr-1 h-3 w-3" />
                                                    View Log
                                                </Link>
                                            </Button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border p-12 text-center text-muted-foreground">
                                        <Play className="h-8 w-8 opacity-40 mb-2" />
                                        <p className="text-sm">Ready to execute</p>
                                        <p className="text-xs text-muted-foreground mt-1 max-w-xs">
                                            Configure your arguments and click "Execute Tool" to
                                            view response payloads.
                                        </p>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>
            ) : (
                <Card className="border-dashed p-12 text-center">
                    <Wrench className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-50" />
                    <h3 className="text-base font-semibold text-foreground">No Tool Selected</h3>
                    <p className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">
                        Choose an MCP server and tool from the selector above to test interactive
                        invocations.
                    </p>
                </Card>
            )}

            {/* Confirmation Dialog for Destructive Tools */}
            <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
                            <AlertTriangle className="h-5 w-5" />
                            Potentially Destructive Action
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            Tool <strong>"{currentTool?.name}"</strong> has an action name
                            indicating write, delete, or system execution. Are you sure you want to
                            run this tool on server <strong>"{currentTool?.server_name}"</strong>?
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={() => {
                                setConfirmOpen(false);
                                runTool(formValues);
                            }}
                            className="bg-amber-600 hover:bg-amber-700 text-white"
                        >
                            Proceed & Execute
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
