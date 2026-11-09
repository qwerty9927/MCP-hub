"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ServerRead, ServerTestResponse } from "@/types";
import {
    useConnectServer,
    useDeleteServer,
    useDisconnectServer,
    useRefreshServerTools,
    useTestServerConnection,
    useUpdateServer,
} from "../hooks/use-servers";
import { HealthBadge } from "@/components/common/HealthBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
    MoreHorizontal,
    Play,
    Square,
    Activity,
    RefreshCw,
    Edit,
    Trash2,
    ExternalLink,
    Terminal,
    Globe,
    Loader2,
    CheckCircle2,
    XCircle,
} from "lucide-react";
import { formatDate } from "@/lib/utils";

interface ServerListTableProps {
    servers: ServerRead[];
    isLoading?: boolean;
}

export function ServerListTable({ servers, isLoading }: ServerListTableProps) {
    const [deleteTarget, setDeleteTarget] = useState<ServerRead | null>(null);
    const [testResult, setTestResult] = useState<{
        server: ServerRead;
        result: ServerTestResponse;
    } | null>(null);

    const deleteMutation = useDeleteServer();
    const connectMutation = useConnectServer();
    const disconnectMutation = useDisconnectServer();
    const testMutation = useTestServerConnection();
    const refreshToolsMutation = useRefreshServerTools();
    const updateMutation = useUpdateServer();

    const handleToggleEnabled = (server: ServerRead) => {
        updateMutation.mutate({
            id: server.id,
            payload: { enabled: !server.enabled },
        });
    };

    const handleTestConnection = async (server: ServerRead) => {
        try {
            const res = await testMutation.mutateAsync(server.id);
            setTestResult({ server, result: res });
        } catch {
            // Handled by mutation toast
        }
    };

    const handleDeleteConfirm = async () => {
        if (!deleteTarget) return;
        try {
            await deleteMutation.mutateAsync(deleteTarget.id);
            setDeleteTarget(null);
        } catch {
            // Handled by toast
        }
    };

    return (
        <>
            <div className="rounded-md border border-border bg-card">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Server Name</TableHead>
                            <TableHead>Transport</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead>Enabled</TableHead>
                            <TableHead className="text-center">Tools</TableHead>
                            <TableHead>Last Connected</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {servers.map((server) => {
                            const isConnecting = connectMutation.isPending && connectMutation.variables === server.id;
                            const isDisconnecting = disconnectMutation.isPending && disconnectMutation.variables === server.id;
                            const isTesting = testMutation.isPending && testMutation.variables === server.id;
                            const isRefreshing = refreshToolsMutation.isPending && refreshToolsMutation.variables === server.id;

                            return (
                                <TableRow key={server.id} className="group">
                                    <TableCell className="font-medium">
                                        <div className="flex flex-col">
                                            <Link
                                                href={`/servers/${server.id}`}
                                                className="font-semibold text-foreground hover:text-primary transition-colors flex items-center gap-1.5"
                                            >
                                                {server.name}
                                                <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                                            </Link>
                                            {server.description && (
                                                <span className="text-xs text-muted-foreground line-clamp-1 max-w-xs mt-0.5">
                                                    {server.description}
                                                </span>
                                            )}
                                        </div>
                                    </TableCell>

                                    <TableCell>
                                        {server.transport === "stdio" ? (
                                            <Badge variant="outline" className="gap-1 text-xs">
                                                <Terminal className="h-3 w-3 text-primary" />
                                                stdio
                                            </Badge>
                                        ) : (
                                            <Badge variant="outline" className="gap-1 text-xs">
                                                <Globe className="h-3 w-3 text-emerald-500" />
                                                HTTP
                                            </Badge>
                                        )}
                                    </TableCell>

                                    <TableCell>
                                        <HealthBadge status={server.health_status} />
                                    </TableCell>

                                    <TableCell>
                                        <Switch
                                            checked={server.enabled}
                                            onCheckedChange={() => handleToggleEnabled(server)}
                                            disabled={updateMutation.isPending}
                                            aria-label="Toggle server enabled"
                                        />
                                    </TableCell>

                                    <TableCell className="text-center">
                                        <Link
                                            href={`/servers/${server.id}`}
                                            className="inline-flex items-center justify-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-semibold hover:bg-primary/20 transition-colors"
                                        >
                                            {server.discovered_tool_count}
                                        </Link>
                                    </TableCell>

                                    <TableCell className="text-xs text-muted-foreground">{formatDate(server.last_connected_at)}</TableCell>

                                    <TableCell className="text-right">
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8"
                                                    disabled={isConnecting || isDisconnecting || isTesting || isRefreshing}
                                                >
                                                    {isConnecting || isDisconnecting || isTesting || isRefreshing ? (
                                                        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                                                    ) : (
                                                        <MoreHorizontal className="h-4 w-4" />
                                                    )}
                                                    <span className="sr-only">Open menu</span>
                                                </Button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="end" className="w-48">
                                                <DropdownMenuItem asChild>
                                                    <Link href={`/servers/${server.id}`} className="cursor-pointer">
                                                        <ExternalLink className="mr-2 h-4 w-4 text-muted-foreground" />
                                                        View Details
                                                    </Link>
                                                </DropdownMenuItem>

                                                <DropdownMenuItem onClick={() => handleTestConnection(server)} className="cursor-pointer">
                                                    <Activity className="mr-2 h-4 w-4 text-muted-foreground" />
                                                    Test Connection
                                                </DropdownMenuItem>

                                                {server.health_status === "HEALTHY" ? (
                                                    <DropdownMenuItem
                                                        onClick={() => disconnectMutation.mutate(server.id)}
                                                        className="cursor-pointer"
                                                    >
                                                        <Square className="mr-2 h-4 w-4 text-amber-500" />
                                                        Disconnect
                                                    </DropdownMenuItem>
                                                ) : (
                                                    <DropdownMenuItem
                                                        onClick={() => connectMutation.mutate(server.id)}
                                                        className="cursor-pointer"
                                                    >
                                                        <Play className="mr-2 h-4 w-4 text-emerald-500" />
                                                        Connect & Discover
                                                    </DropdownMenuItem>
                                                )}

                                                <DropdownMenuItem
                                                    onClick={() => refreshToolsMutation.mutate(server.id)}
                                                    className="cursor-pointer"
                                                >
                                                    <RefreshCw className="mr-2 h-4 w-4 text-muted-foreground" />
                                                    Refresh Tools
                                                </DropdownMenuItem>

                                                <DropdownMenuSeparator />

                                                <DropdownMenuItem asChild>
                                                    <Link href={`/servers/${server.id}/edit`} className="cursor-pointer">
                                                        <Edit className="mr-2 h-4 w-4 text-muted-foreground" />
                                                        Edit Configuration
                                                    </Link>
                                                </DropdownMenuItem>

                                                <DropdownMenuItem
                                                    onClick={() => setDeleteTarget(server)}
                                                    className="cursor-pointer text-destructive focus:text-destructive"
                                                >
                                                    <Trash2 className="mr-2 h-4 w-4" />
                                                    Delete Server
                                                </DropdownMenuItem>
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                    </TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </div>

            {/* Delete Confirmation Alert Dialog */}
            <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && setDeleteTarget(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will permanently delete the server <strong className="text-foreground">"{deleteTarget?.name}"</strong>,
                            terminate any active connection sessions, and remove all its discovered tools from the MCP catalog. This action
                            cannot be undone.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={deleteMutation.isPending}>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleDeleteConfirm}
                            disabled={deleteMutation.isPending}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90 gap-2"
                        >
                            {deleteMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                            Delete Server
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            {/* Connection Test Result Dialog */}
            <Dialog open={Boolean(testResult)} onOpenChange={(open) => !open && setTestResult(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            {testResult?.result.success ? (
                                <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                            ) : (
                                <XCircle className="h-5 w-5 text-destructive" />
                            )}
                            Connection Test Result
                        </DialogTitle>
                        <DialogDescription>
                            Test probe for server: <span className="font-semibold text-foreground">{testResult?.server.name}</span>
                        </DialogDescription>
                    </DialogHeader>

                    {testResult && (
                        <div className="space-y-3 pt-2">
                            <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
                                <p className="font-medium text-foreground">{testResult.result.message}</p>
                            </div>

                            <div className="grid grid-cols-2 gap-3 text-sm">
                                <div className="rounded-lg border border-border p-3">
                                    <span className="text-xs text-muted-foreground">Latency</span>
                                    <p className="text-lg font-bold font-mono text-foreground mt-0.5">
                                        {testResult.result.latency_ms.toFixed(1)} ms
                                    </p>
                                </div>
                                <div className="rounded-lg border border-border p-3">
                                    <span className="text-xs text-muted-foreground">Discovered Tools</span>
                                    <p className="text-lg font-bold font-mono text-foreground mt-0.5">{testResult.result.tools_count}</p>
                                </div>
                            </div>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </>
    );
}
