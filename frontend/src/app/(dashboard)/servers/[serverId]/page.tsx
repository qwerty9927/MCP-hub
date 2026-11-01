"use client";

import React, { use, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
    ArrowLeft,
    Activity,
    Play,
    Square,
    RefreshCw,
    Edit,
    Trash2,
    Terminal,
    Globe,
    Wrench,
    Loader2,
    CheckCircle2,
    XCircle,
    Clock,
    Shield,
    Layers,
    History,
    AlertTriangle,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { HealthBadge } from "@/components/common/HealthBadge";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
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
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { EmptyState } from "@/components/common/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatDuration } from "@/lib/utils";
import {
    useConnectServer,
    useDeleteServer,
    useDisconnectServer,
    useRefreshServerTools,
    useServer,
    useServerTools,
    useTestServerConnection,
} from "@/features/servers/hooks/use-servers";
import { useExecutions } from "@/features/executions/hooks/use-executions";
import { ServerTestResponse } from "@/types";

interface ServerDetailPageProps {
    params: Promise<{ serverId: string }>;
}

export default function ServerDetailPage({ params }: ServerDetailPageProps) {
    const { serverId } = use(params);
    const router = useRouter();

    const [deleteOpen, setDeleteOpen] = useState(false);
    const [testResult, setTestResult] = useState<ServerTestResponse | null>(null);

    const { data: server, isLoading, isError, error, refetch } = useServer(serverId);
    const { data: toolsData, isLoading: toolsLoading } = useServerTools(serverId);
    const { data: executionsData, isLoading: executionsLoading } = useExecutions({
        server_id: serverId,
        page: 1,
        page_size: 10,
    });

    const connectMutation = useConnectServer();
    const disconnectMutation = useDisconnectServer();
    const testMutation = useTestServerConnection();
    const refreshToolsMutation = useRefreshServerTools();
    const deleteMutation = useDeleteServer();

    const handleTestConnection = async () => {
        try {
            const res = await testMutation.mutateAsync(serverId);
            setTestResult(res);
        } catch {
            // Handled by toast
        }
    };

    const handleDelete = async () => {
        try {
            await deleteMutation.mutateAsync(serverId);
            router.push("/servers");
        } catch {
            // Handled by toast
        }
    };

    if (isLoading) {
        return (
            <div className="space-y-6">
                <Skeleton className="h-8 w-48" />
                <Skeleton className="h-24 w-full" />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Skeleton className="h-48 w-full" />
                    <Skeleton className="h-48 w-full" />
                </div>
            </div>
        );
    }

    if (isError || !server) {
        return (
            <div className="space-y-6">
                <Button asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
                    <Link href="/servers">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Servers
                    </Link>
                </Button>
                <ErrorAlert
                    title="Server Not Found"
                    message={
                        (error as any)?.message ||
                        "The requested MCP server does not exist or has been removed."
                    }
                    correlationId={(error as any)?.correlationId}
                    onRetry={() => refetch()}
                />
            </div>
        );
    }

    const isActionLoading =
        connectMutation.isPending ||
        disconnectMutation.isPending ||
        testMutation.isPending ||
        refreshToolsMutation.isPending;

    const tools = toolsData?.items || [];
    const executions = executionsData?.items || [];

    return (
        <div className="space-y-6">
            {/* Navigation Breadcrumb */}
            <div className="flex items-center gap-2">
                <Button asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
                    <Link href="/servers">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Servers
                    </Link>
                </Button>
            </div>

            {/* Header and Controls */}
            <PageHeader
                title={server.name}
                description={server.description || "No description provided."}
                actions={
                    <div className="flex flex-wrap items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleTestConnection}
                            disabled={isActionLoading}
                            className="gap-1.5"
                        >
                            {testMutation.isPending ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <Activity className="h-4 w-4 text-primary" />
                            )}
                            Test Connection
                        </Button>

                        {server.health_status === "HEALTHY" ? (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => disconnectMutation.mutate(server.id)}
                                disabled={isActionLoading}
                                className="gap-1.5 text-amber-600 dark:text-amber-400 border-amber-500/30"
                            >
                                {disconnectMutation.isPending ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <Square className="h-4 w-4" />
                                )}
                                Disconnect
                            </Button>
                        ) : (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => connectMutation.mutate(server.id)}
                                disabled={isActionLoading}
                                className="gap-1.5 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                            >
                                {connectMutation.isPending ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <Play className="h-4 w-4" />
                                )}
                                Connect
                            </Button>
                        )}

                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => refreshToolsMutation.mutate(server.id)}
                            disabled={isActionLoading}
                            className="gap-1.5"
                        >
                            {refreshToolsMutation.isPending ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <RefreshCw className="h-4 w-4" />
                            )}
                            Refresh Tools
                        </Button>

                        <Button asChild variant="outline" size="sm" className="gap-1.5">
                            <Link href={`/servers/${server.id}/edit`}>
                                <Edit className="h-4 w-4" />
                                Edit
                            </Link>
                        </Button>

                        <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => setDeleteOpen(true)}
                            disabled={isActionLoading}
                            className="gap-1.5"
                        >
                            <Trash2 className="h-4 w-4" />
                            Delete
                        </Button>
                    </div>
                }
            />

            {/* Status Highlights */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">Health Status</span>
                    <div className="mt-2">
                        <HealthBadge status={server.health_status} />
                    </div>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">
                        Transport Protocol
                    </span>
                    <div className="mt-2 flex items-center gap-1.5">
                        {server.transport === "stdio" ? (
                            <Badge variant="outline" className="gap-1 font-mono text-xs">
                                <Terminal className="h-3 w-3 text-primary" />
                                stdio
                            </Badge>
                        ) : (
                            <Badge variant="outline" className="gap-1 font-mono text-xs">
                                <Globe className="h-3 w-3 text-emerald-500" />
                                streamable-http
                            </Badge>
                        )}
                    </div>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">
                        Execution Status
                    </span>
                    <div className="mt-2">
                        {server.enabled ? (
                            <Badge variant="success">Enabled</Badge>
                        ) : (
                            <Badge variant="secondary">Disabled</Badge>
                        )}
                    </div>
                </Card>

                <Card className="p-4">
                    <span className="text-xs text-muted-foreground font-medium">
                        Discovered Tools
                    </span>
                    <p className="mt-1 text-2xl font-bold font-mono text-foreground">
                        {server.discovered_tool_count}
                    </p>
                </Card>
            </div>

            {/* Unhealthy Server Alert Banner */}
            {server.health_status === "UNHEALTHY" && (
                <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-destructive">
                    <div className="flex items-start gap-3">
                        <AlertTriangle className="h-5 w-5 mt-0.5 shrink-0" />
                        <div className="flex-1 space-y-1">
                            <h4 className="font-semibold text-sm">Server Connectivity Failure</h4>
                            <p className="text-sm opacity-90">
                                This MCP server failed its health check or subprocess communication
                                broke down. Discovered tools are currently unavailable for execution
                                until connectivity is re-established.
                            </p>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleTestConnection}
                            disabled={isActionLoading}
                            className="shrink-0 border-destructive/40 hover:bg-destructive/20 text-destructive dark:text-red-300"
                        >
                            <Activity className="mr-1.5 h-3.5 w-3.5" />
                            Retest Connection
                        </Button>
                    </div>
                </div>
            )}

            {/* Detailed Information Tabs */}
            <Tabs defaultValue="tools" className="w-full">
                <TabsList className="grid w-full grid-cols-4 max-w-xl">
                    <TabsTrigger value="tools" className="gap-1.5">
                        <Wrench className="h-4 w-4" />
                        Tools ({tools.length})
                    </TabsTrigger>
                    <TabsTrigger value="executions" className="gap-1.5">
                        <History className="h-4 w-4" />
                        Executions ({executions.length})
                    </TabsTrigger>
                    <TabsTrigger value="config" className="gap-1.5">
                        <Layers className="h-4 w-4" />
                        Configuration
                    </TabsTrigger>
                    <TabsTrigger value="telemetry" className="gap-1.5">
                        <Clock className="h-4 w-4" />
                        Timestamps
                    </TabsTrigger>
                </TabsList>

                {/* Tools Tab */}
                <TabsContent value="tools" className="mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Discovered MCP Tools</CardTitle>
                            <CardDescription>
                                Tools provided by this server that can be executed from the
                                playground or REST API.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {toolsLoading ? (
                                <div className="space-y-2">
                                    <Skeleton className="h-10 w-full" />
                                    <Skeleton className="h-10 w-full" />
                                </div>
                            ) : tools.length === 0 ? (
                                <EmptyState
                                    icon={Wrench}
                                    title="No tools discovered"
                                    description="Connect to the server or refresh tools to discover available capabilities."
                                    action={
                                        <Button
                                            size="sm"
                                            onClick={() => refreshToolsMutation.mutate(server.id)}
                                            disabled={refreshToolsMutation.isPending}
                                        >
                                            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                                            Discover Tools Now
                                        </Button>
                                    }
                                />
                            ) : (
                                <div className="rounded-md border border-border">
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Tool Name</TableHead>
                                                <TableHead>Description</TableHead>
                                                <TableHead>Parameters</TableHead>
                                                <TableHead className="text-right">Action</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {tools.map((tool) => {
                                                const requiredParams =
                                                    tool.input_schema?.required?.length || 0;
                                                const totalProps = Object.keys(
                                                    tool.input_schema?.properties || {}
                                                ).length;

                                                return (
                                                    <TableRow key={tool.id}>
                                                        <TableCell className="font-mono font-medium">
                                                            <Link
                                                                href={`/tools/${encodeURIComponent(tool.id)}`}
                                                                className="hover:underline text-foreground hover:text-primary transition-colors"
                                                            >
                                                                {tool.name}
                                                            </Link>
                                                        </TableCell>
                                                        <TableCell className="text-muted-foreground text-xs max-w-md">
                                                            {tool.description || "No description"}
                                                        </TableCell>
                                                        <TableCell className="text-xs">
                                                            <span className="font-mono bg-muted px-2 py-0.5 rounded">
                                                                {totalProps} props ({requiredParams}{" "}
                                                                required)
                                                            </span>
                                                        </TableCell>
                                                        <TableCell className="text-right">
                                                            <Button
                                                                asChild
                                                                size="sm"
                                                                variant="outline"
                                                            >
                                                                <Link
                                                                    href={`/playground?server=${server.id}&tool=${encodeURIComponent(
                                                                        tool.name
                                                                    )}`}
                                                                >
                                                                    Run in Playground
                                                                </Link>
                                                            </Button>
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

                {/* Executions Tab */}
                <TabsContent value="executions" className="mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Recent Tool Invocations</CardTitle>
                            <CardDescription>
                                Historical execution logs and latency benchmarks strictly for this
                                MCP server.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {executionsLoading ? (
                                <div className="space-y-2">
                                    <Skeleton className="h-10 w-full" />
                                    <Skeleton className="h-10 w-full" />
                                </div>
                            ) : executions.length === 0 ? (
                                <EmptyState
                                    icon={History}
                                    title="No execution records"
                                    description="No tools on this server have been executed yet. Run a tool in the Playground to see results logged here."
                                    action={
                                        <Button asChild size="sm">
                                            <Link href={`/playground?server=${server.id}`}>
                                                Open Playground
                                            </Link>
                                        </Button>
                                    }
                                />
                            ) : (
                                <div className="rounded-md border border-border">
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Status</TableHead>
                                                <TableHead>Tool</TableHead>
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
                                                    <TableRow key={exec.id}>
                                                        <TableCell>
                                                            {exec.is_error ? (
                                                                <Badge
                                                                    variant="destructive"
                                                                    className="gap-1 font-medium text-xs"
                                                                >
                                                                    <XCircle className="h-3 w-3" />
                                                                    Failed
                                                                </Badge>
                                                            ) : (
                                                                <Badge
                                                                    variant="success"
                                                                    className="gap-1 font-medium text-xs"
                                                                >
                                                                    <CheckCircle2 className="h-3 w-3" />
                                                                    Success
                                                                </Badge>
                                                            )}
                                                        </TableCell>
                                                        <TableCell className="font-mono font-medium text-sm">
                                                            {exec.tool_name}
                                                        </TableCell>
                                                        <TableCell className="max-w-xs text-xs font-mono text-muted-foreground truncate">
                                                            {argsString === "{}" ? "-" : argsString}
                                                        </TableCell>
                                                        <TableCell className="text-xs font-mono">
                                                            {formatDuration(exec.duration_ms)}
                                                        </TableCell>
                                                        <TableCell className="text-xs text-muted-foreground">
                                                            {formatDate(exec.executed_at)}
                                                        </TableCell>
                                                        <TableCell className="text-right">
                                                            <Button
                                                                asChild
                                                                size="sm"
                                                                variant="outline"
                                                                className="h-8 text-xs"
                                                            >
                                                                <Link
                                                                    href={`/executions/${exec.id}`}
                                                                >
                                                                    Details
                                                                </Link>
                                                            </Button>
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

                {/* Configuration Tab */}
                <TabsContent value="config" className="mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">
                                Sanitized Connection Configuration
                            </CardTitle>
                            <CardDescription>
                                Parameters used to initialize client sessions. Sensitive
                                authentication credentials are redacted.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {server.transport === "stdio" ? (
                                <div className="space-y-4">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div className="rounded-lg border border-border p-3">
                                            <span className="text-xs text-muted-foreground font-medium">
                                                Command
                                            </span>
                                            <p className="mt-1 font-mono text-sm font-semibold text-foreground">
                                                {server.connection_config.command || "-"}
                                            </p>
                                        </div>

                                        <div className="rounded-lg border border-border p-3">
                                            <span className="text-xs text-muted-foreground font-medium">
                                                Arguments
                                            </span>
                                            <p className="mt-1 font-mono text-sm text-foreground">
                                                {server.connection_config.args?.join(" ") || "None"}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    <div className="rounded-lg border border-border p-3">
                                        <span className="text-xs text-muted-foreground font-medium">
                                            Endpoint URL
                                        </span>
                                        <p className="mt-1 font-mono text-sm font-semibold text-foreground break-all">
                                            {server.connection_config.url || "-"}
                                        </p>
                                    </div>

                                    <div className="rounded-lg border border-border p-3">
                                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium mb-2">
                                            <Shield className="h-3.5 w-3.5 text-emerald-500" />
                                            <span>HTTP Headers (Masked)</span>
                                        </div>
                                        {server.connection_config.headers &&
                                        Object.keys(server.connection_config.headers).length > 0 ? (
                                            <pre className="font-mono text-xs bg-muted p-2 rounded overflow-x-auto">
                                                {JSON.stringify(
                                                    server.connection_config.headers,
                                                    null,
                                                    2
                                                )}
                                            </pre>
                                        ) : (
                                            <p className="text-xs text-muted-foreground">
                                                No custom headers configured.
                                            </p>
                                        )}
                                    </div>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Timestamps Tab */}
                <TabsContent value="telemetry" className="mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Lifecycle & Health Checks</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                                <div className="rounded-lg border border-border p-3">
                                    <dt className="text-xs text-muted-foreground">
                                        Last Connected At
                                    </dt>
                                    <dd className="mt-1 font-mono font-medium text-foreground">
                                        {formatDate(server.last_connected_at)}
                                    </dd>
                                </div>
                                <div className="rounded-lg border border-border p-3">
                                    <dt className="text-xs text-muted-foreground">
                                        Last Health Check At
                                    </dt>
                                    <dd className="mt-1 font-mono font-medium text-foreground">
                                        {formatDate(server.last_health_check_at)}
                                    </dd>
                                </div>
                                <div className="rounded-lg border border-border p-3">
                                    <dt className="text-xs text-muted-foreground">Registered At</dt>
                                    <dd className="mt-1 font-mono font-medium text-foreground">
                                        {formatDate(server.created_at)}
                                    </dd>
                                </div>
                                <div className="rounded-lg border border-border p-3">
                                    <dt className="text-xs text-muted-foreground">
                                        Last Updated At
                                    </dt>
                                    <dd className="mt-1 font-mono font-medium text-foreground">
                                        {formatDate(server.updated_at)}
                                    </dd>
                                </div>
                            </dl>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            {/* Delete Confirmation Alert Dialog */}
            <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This action will permanently delete server{" "}
                            <strong>"{server.name}"</strong>, terminate all active transport
                            sessions, and purge its tools from the catalog.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={deleteMutation.isPending}>
                            Cancel
                        </AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleDelete}
                            disabled={deleteMutation.isPending}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90 gap-2"
                        >
                            {deleteMutation.isPending && (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            )}
                            Confirm Delete
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            {/* Connection Test Result Dialog */}
            <Dialog
                open={Boolean(testResult)}
                onOpenChange={(open) => !open && setTestResult(null)}
            >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            {testResult?.success ? (
                                <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                            ) : (
                                <XCircle className="h-5 w-5 text-destructive" />
                            )}
                            Connection Test Result
                        </DialogTitle>
                        <DialogDescription>
                            Connectivity check to{" "}
                            <strong className="text-foreground">{server.name}</strong>
                        </DialogDescription>
                    </DialogHeader>

                    {testResult && (
                        <div className="space-y-3 pt-2">
                            <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
                                <p className="font-medium text-foreground">{testResult.message}</p>
                            </div>

                            <div className="grid grid-cols-2 gap-3 text-sm">
                                <div className="rounded-lg border border-border p-3">
                                    <span className="text-xs text-muted-foreground">Latency</span>
                                    <p className="text-lg font-bold font-mono text-foreground mt-0.5">
                                        {testResult.latency_ms.toFixed(1)} ms
                                    </p>
                                </div>
                                <div className="rounded-lg border border-border p-3">
                                    <span className="text-xs text-muted-foreground">
                                        Discovered Tools
                                    </span>
                                    <p className="text-lg font-bold font-mono text-foreground mt-0.5">
                                        {testResult.tools_count}
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    );
}
