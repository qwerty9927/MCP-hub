"use client";

import React, { use } from "react";
import Link from "next/link";
import { ArrowLeft, Play, Server, Code, FileText, CheckCircle2 } from "lucide-react";
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
    const decodedToolId = decodeURIComponent(toolId);

    const { data: tool, isLoading, isError, error, refetch } = useTool(decodedToolId);

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

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">Server</span>
                    <div className="mt-2 flex items-center gap-2">
                        <Server className="h-4 w-4 text-primary" />
                        <Link
                            href={`/servers/${tool.server_id}`}
                            className="font-medium text-foreground hover:underline"
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
                    <span className="text-xs text-muted-foreground font-medium">
                        Last Discovered
                    </span>
                    <p className="mt-2 text-sm font-mono text-foreground">
                        {formatDate(tool.last_discovered_at)}
                    </p>
                </Card>
            </div>

            <Tabs defaultValue="schema" className="w-full">
                <TabsList className="grid w-full grid-cols-2 max-w-xs">
                    <TabsTrigger value="schema" className="gap-1.5">
                        <FileText className="h-4 w-4" />
                        Input Parameters ({propertyEntries.length})
                    </TabsTrigger>
                    <TabsTrigger value="raw" className="gap-1.5">
                        <Code className="h-4 w-4" />
                        Raw JSON Schema
                    </TabsTrigger>
                </TabsList>

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
                                <div className="rounded-md border border-border">
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Field</TableHead>
                                                <TableHead>Type</TableHead>
                                                <TableHead>Required</TableHead>
                                                <TableHead>Description</TableHead>
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
                                                        <TableCell className="text-xs text-muted-foreground max-w-md">
                                                            {prop.description || "-"}
                                                            {prop.enum && (
                                                                <div className="mt-1 flex flex-wrap gap-1">
                                                                    {prop.enum.map((val: any) => (
                                                                        <span
                                                                            key={val}
                                                                            className="rounded border border-border px-1.5 py-0.5 text-[11px] font-mono"
                                                                        >
                                                                            {String(val)}
                                                                        </span>
                                                                    ))}
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

                <TabsContent value="raw" className="mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">JSON Schema</CardTitle>
                            <CardDescription>
                                Complete standard JSON Schema specification returned by MCP server.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <pre className="rounded-lg bg-muted/60 p-4 font-mono text-xs overflow-x-auto border border-border">
                                {JSON.stringify(tool.input_schema, null, 2)}
                            </pre>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}
