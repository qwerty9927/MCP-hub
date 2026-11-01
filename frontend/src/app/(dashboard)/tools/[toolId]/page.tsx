"use client";

import React, { use, useState } from "react";
import Link from "next/link";
import {
    ArrowLeft,
    Play,
    Server,
    Code,
    FileText,
    CheckCircle2,
    Copy,
    Check,
    Terminal,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common/PageHeader";
import { HealthBadge } from "@/components/common/HealthBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { useTool } from "@/features/tools/hooks/use-tools";
import { formatDate } from "@/lib/utils";

interface ToolDetailPageProps {
    params: Promise<{ toolId: string }>;
}

export default function ToolDetailPage({ params }: ToolDetailPageProps) {
    const { toolId } = use(params);

    let decodedToolId = toolId;
    try {
        decodedToolId = decodeURIComponent(toolId);
    } catch {
        decodedToolId = toolId;
    }

    const { data: tool, isLoading, isError, error, refetch } = useTool(decodedToolId);

    const [activeTab, setActiveTab] = useState<string>("schema");
    const [copiedSnippet, setCopiedSnippet] = useState<string | null>(null);

    const copyToClipboard = (text: string, label: string) => {
        navigator.clipboard.writeText(text);
        setCopiedSnippet(label);
        setTimeout(() => setCopiedSnippet(null), 2000);
        toast.success(`${label} copied to clipboard`);
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

    if (isError || !tool) {
        return (
            <div className="space-y-6">
                <Button asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
                    <Link href="/tools">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Tool Catalog
                    </Link>
                </Button>
                <ErrorAlert
                    title="Tool Not Found"
                    message={(error as any)?.message || "The requested tool could not be found."}
                    onRetry={() => refetch()}
                />
            </div>
        );
    }

    const properties = tool.input_schema?.properties || {};
    const requiredList: string[] = tool.input_schema?.required || [];
    const propertyEntries = Object.entries(properties);

    // Build sample arguments object
    const sampleArgs: Record<string, any> = {};
    for (const [k, v] of Object.entries<any>(properties)) {
        if (v.default !== undefined) {
            sampleArgs[k] = v.default;
        } else if (v.type === "integer" || v.type === "number") {
            sampleArgs[k] = 0;
        } else if (v.type === "boolean") {
            sampleArgs[k] = true;
        } else if (v.type === "array") {
            sampleArgs[k] = [];
        } else if (v.type === "object") {
            sampleArgs[k] = {};
        } else if (v.enum && v.enum.length > 0) {
            sampleArgs[k] = v.enum[0];
        } else {
            sampleArgs[k] = `sample_${k}`;
        }
    }

    const curlSnippet = `curl -X POST http://localhost:8000/api/v1/servers/${tool.server_id}/tools/${encodeURIComponent(
        tool.name
    )}/execute \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify({ arguments: sampleArgs }, null, 2)}'`;

    const pythonGatewaySnippet = `# Invoking via MCP Hub Unified Gateway (/mcp)
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

async with streamable_http_client("http://localhost:8000/mcp") as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        result = await session.call_tool(
            "${tool.server_name.toLowerCase().replace(/[^a-z0-9_]/g, "_")}__${tool.name}",
            arguments=${JSON.stringify(sampleArgs, null, 4)}
        )
        print(result.content[0].text)`;

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-2">
                <Button asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
                    <Link href="/tools">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Tool Catalog
                    </Link>
                </Button>
            </div>

            <PageHeader
                title={tool.name}
                description={tool.description || "No description provided by server."}
                actions={
                    <Button asChild className="gap-2">
                        <Link
                            href={`/playground?server=${tool.server_id}&tool=${encodeURIComponent(
                                tool.name
                            )}`}
                        >
                            <Play className="h-4 w-4" />
                            Test in Playground
                        </Link>
                    </Button>
                }
            />

            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">Server</span>
                    <div className="mt-2 flex items-center gap-2">
                        <Server className="h-4 w-4 text-primary shrink-0" />
                        <Link
                            href={`/servers/${tool.server_id}`}
                            className="font-medium text-foreground hover:underline truncate"
                        >
                            {tool.server_name}
                        </Link>
                    </div>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">Availability</span>
                    <div className="mt-2">
                        <HealthBadge status={tool.availability_status} />
                    </div>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">Qualified ID</span>
                    <div className="mt-2 flex items-center justify-between gap-1">
                        <code
                            className="text-xs font-mono text-foreground truncate"
                            title={tool.id}
                        >
                            {tool.id}
                        </code>
                        <button
                            type="button"
                            onClick={() => copyToClipboard(tool.id, "Tool ID")}
                            className="text-muted-foreground hover:text-foreground shrink-0"
                            title="Copy ID"
                        >
                            {copiedSnippet === "Tool ID" ? (
                                <Check className="h-3.5 w-3.5 text-emerald-500" />
                            ) : (
                                <Copy className="h-3.5 w-3.5" />
                            )}
                        </button>
                    </div>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">
                        Last Discovered
                    </span>
                    <p className="mt-2 text-sm font-mono text-foreground">
                        {formatDate(tool.last_discovered_at)}
                    </p>
                </Card>
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="grid w-full grid-cols-3 max-w-md">
                    <TabsTrigger
                        value="schema"
                        onClick={() => setActiveTab("schema")}
                        className="gap-1.5"
                    >
                        <FileText className="h-4 w-4" />
                        Parameters ({propertyEntries.length})
                    </TabsTrigger>
                    <TabsTrigger
                        value="raw"
                        onClick={() => setActiveTab("raw")}
                        className="gap-1.5"
                    >
                        <Code className="h-4 w-4" />
                        JSON Schema
                    </TabsTrigger>
                    <TabsTrigger
                        value="code"
                        onClick={() => setActiveTab("code")}
                        className="gap-1.5"
                    >
                        <Terminal className="h-4 w-4" />
                        Invocation API
                    </TabsTrigger>
                </TabsList>

                {/* Schema Tab */}
                <TabsContent value="schema" className="mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Input Schema Fields</CardTitle>
                            <CardDescription>
                                Parameters accepted by this tool when executing an invocation
                                request.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {propertyEntries.length === 0 ? (
                                <p className="text-sm text-muted-foreground">
                                    This tool accepts no arguments (empty input schema).
                                </p>
                            ) : (
                                <div className="rounded-md border border-border overflow-hidden">
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Field</TableHead>
                                                <TableHead>Type</TableHead>
                                                <TableHead>Required</TableHead>
                                                <TableHead>Default</TableHead>
                                                <TableHead>Description & Constraints</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {propertyEntries.map(([name, prop]: [string, any]) => {
                                                const isRequired = requiredList.includes(name);

                                                return (
                                                    <TableRow key={name}>
                                                        <TableCell className="font-mono font-semibold">
                                                            {name}
                                                        </TableCell>
                                                        <TableCell>
                                                            <span className="rounded bg-muted px-2 py-0.5 font-mono text-xs text-primary">
                                                                {prop.type || "any"}
                                                                {prop.format
                                                                    ? ` (${prop.format})`
                                                                    : ""}
                                                            </span>
                                                        </TableCell>
                                                        <TableCell>
                                                            {isRequired ? (
                                                                <span className="inline-flex items-center gap-1 text-xs font-semibold text-destructive">
                                                                    <CheckCircle2 className="h-3 w-3" />
                                                                    Required
                                                                </span>
                                                            ) : (
                                                                <span className="text-xs text-muted-foreground">
                                                                    Optional
                                                                </span>
                                                            )}
                                                        </TableCell>
                                                        <TableCell className="font-mono text-xs text-muted-foreground">
                                                            {prop.default !== undefined
                                                                ? String(prop.default)
                                                                : "-"}
                                                        </TableCell>
                                                        <TableCell className="text-xs text-muted-foreground max-w-md space-y-1">
                                                            <p>{prop.description || "-"}</p>
                                                            {prop.enum && (
                                                                <div className="flex flex-wrap items-center gap-1 mt-1">
                                                                    <span className="text-[11px] font-medium text-foreground">
                                                                        Enum:
                                                                    </span>
                                                                    {prop.enum.map((val: any) => (
                                                                        <span
                                                                            key={String(val)}
                                                                            className="rounded border border-border px-1.5 py-0.2 text-[10px] font-mono bg-muted/40"
                                                                        >
                                                                            {String(val)}
                                                                        </span>
                                                                    ))}
                                                                </div>
                                                            )}
                                                            {(prop.minimum !== undefined ||
                                                                prop.maximum !== undefined) && (
                                                                <div className="text-[11px] font-mono text-muted-foreground">
                                                                    Range: [{prop.minimum ?? "-∞"},{" "}
                                                                    {prop.maximum ?? "+∞"}]
                                                                </div>
                                                            )}
                                                        </TableCell>
                                                    </TableRow>
                                                );
                                            })}
                                        </TableBody>
                                    </Table>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Raw JSON Schema Tab */}
                <TabsContent value="raw" className="mt-4">
                    <Card>
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="text-lg">JSON Schema</CardTitle>
                                    <CardDescription>
                                        Complete standard JSON Schema specification returned by MCP
                                        server.
                                    </CardDescription>
                                </div>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() =>
                                        copyToClipboard(
                                            JSON.stringify(tool.input_schema, null, 2),
                                            "JSON Schema"
                                        )
                                    }
                                    className="gap-1.5 text-xs"
                                >
                                    {copiedSnippet === "JSON Schema" ? (
                                        <Check className="h-3.5 w-3.5 text-emerald-500" />
                                    ) : (
                                        <Copy className="h-3.5 w-3.5" />
                                    )}
                                    Copy Schema
                                </Button>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <pre className="rounded-lg bg-muted/60 p-4 font-mono text-xs overflow-x-auto border border-border">
                                {JSON.stringify(tool.input_schema, null, 2)}
                            </pre>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Invocation API Snippets Tab */}
                <TabsContent value="code" className="mt-4 space-y-4">
                    <Card>
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <Terminal className="h-4 w-4 text-primary" />
                                        REST API Execution (cURL)
                                    </CardTitle>
                                    <CardDescription>
                                        Execute directly via the MCP Hub backend REST endpoint.
                                    </CardDescription>
                                </div>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => copyToClipboard(curlSnippet, "cURL snippet")}
                                    className="gap-1.5 text-xs"
                                >
                                    {copiedSnippet === "cURL snippet" ? (
                                        <Check className="h-3.5 w-3.5 text-emerald-500" />
                                    ) : (
                                        <Copy className="h-3.5 w-3.5" />
                                    )}
                                    Copy cURL
                                </Button>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <pre className="rounded-lg bg-muted/60 p-4 font-mono text-xs overflow-x-auto border border-border whitespace-pre-wrap">
                                {curlSnippet}
                            </pre>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <Code className="h-4 w-4 text-primary" />
                                        Unified MCP Gateway (/mcp) Python Client
                                    </CardTitle>
                                    <CardDescription>
                                        Connect standard MCP clients directly to the aggregated
                                        streamable gateway.
                                    </CardDescription>
                                </div>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() =>
                                        copyToClipboard(pythonGatewaySnippet, "Python snippet")
                                    }
                                    className="gap-1.5 text-xs"
                                >
                                    {copiedSnippet === "Python snippet" ? (
                                        <Check className="h-3.5 w-3.5 text-emerald-500" />
                                    ) : (
                                        <Copy className="h-3.5 w-3.5" />
                                    )}
                                    Copy Python
                                </Button>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <pre className="rounded-lg bg-muted/60 p-4 font-mono text-xs overflow-x-auto border border-border whitespace-pre-wrap">
                                {pythonGatewaySnippet}
                            </pre>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}
