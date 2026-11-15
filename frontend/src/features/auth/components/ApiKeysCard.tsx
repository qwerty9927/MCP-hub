"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Check, Copy, KeyRound, Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from "@/features/auth/hooks/use-auth";
import { formatDate } from "@/lib/utils";
import { ApiKeyFormValues, apiKeySchema } from "@/schemas/auth.schema";
import { ApiKeyCreated } from "@/types";

function mcpEndpoint(): string {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
    return apiBaseUrl.replace(/\/api\/v1\/?$/, "/mcp");
}

export function mcpClientConfig(key: string): string {
    return JSON.stringify({ mcpServers: { "mcp-hub": { type: "http", url: mcpEndpoint(), headers: { "x-api-key": key } } } }, null, 2);
}

function CopyButton({ value, label }: { value: string; label: string }) {
    const [copied, setCopied] = useState(false);
    const copy = async () => {
        try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            toast.error("Could not copy to the clipboard");
        }
    };
    return (
        <Button type="button" variant="outline" size="sm" onClick={copy} className="h-8 gap-1.5 text-xs" aria-label={label}>
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy"}
        </Button>
    );
}

/** Generate, list and revoke the API keys MCP clients use to reach /mcp on this account's behalf. */
export function ApiKeysCard() {
    const { data: keys, isLoading } = useApiKeys();
    const createKey = useCreateApiKey();
    const revokeKey = useRevokeApiKey();
    const [created, setCreated] = useState<ApiKeyCreated | null>(null);
    const {
        register,
        handleSubmit,
        reset,
        formState: { errors },
    } = useForm<ApiKeyFormValues>({ resolver: zodResolver(apiKeySchema), defaultValues: { name: "" } });

    const onCreate = handleSubmit(async ({ name }) => {
        try {
            setCreated(await createKey.mutateAsync(name));
            reset();
        } catch {
            // Toast from the hook
        }
    });

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                    <KeyRound className="h-4 w-4 text-primary" />
                    API Keys for MCP Clients
                </CardTitle>
                <CardDescription>
                    Each MCP client (Claude, Cursor, a script) should get its own key. Calls from one key are grouped into that
                    client&apos;s sessions, and a key can be revoked on its own.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <form onSubmit={onCreate} className="flex flex-col gap-2 sm:flex-row sm:items-start" noValidate>
                    <div className="flex-1 space-y-1">
                        <Label htmlFor="api-key-name" className="sr-only">
                            Key name
                        </Label>
                        <Input id="api-key-name" placeholder="e.g. laptop Claude" {...register("name")} />
                        {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
                    </div>
                    <Button type="submit" size="sm" className="h-9 gap-1.5" disabled={createKey.isPending}>
                        {createKey.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                        Generate key
                    </Button>
                </form>

                {isLoading ? (
                    <Skeleton className="h-20 w-full" />
                ) : !keys || keys.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No API keys yet.</p>
                ) : (
                    <div className="rounded-md border border-border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Key</TableHead>
                                    <TableHead>Created</TableHead>
                                    <TableHead>Last used</TableHead>
                                    <TableHead className="text-right">Action</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {keys.map((key) => (
                                    <TableRow key={key.id}>
                                        <TableCell className="font-medium">{key.name}</TableCell>
                                        <TableCell className="font-mono text-xs text-muted-foreground">{key.key_prefix}…</TableCell>
                                        <TableCell className="text-xs text-muted-foreground">{formatDate(key.created_at)}</TableCell>
                                        <TableCell className="text-xs text-muted-foreground">{formatDate(key.last_used_at)}</TableCell>
                                        <TableCell className="text-right">
                                            {key.revoked_at ? (
                                                <Badge variant="outline">Revoked</Badge>
                                            ) : (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    className="h-8 text-xs text-destructive"
                                                    disabled={revokeKey.isPending}
                                                    onClick={() => revokeKey.mutate(key.id)}
                                                    aria-label={`Revoke ${key.name}`}
                                                >
                                                    Revoke
                                                </Button>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                )}
            </CardContent>

            <Dialog open={created !== null} onOpenChange={(open) => !open && setCreated(null)}>
                <DialogContent className="max-w-xl">
                    <DialogHeader>
                        <DialogTitle>API key created: {created?.name}</DialogTitle>
                        <DialogDescription>
                            Copy it now. The hub stores only a hash, so this is the only time it is shown.
                        </DialogDescription>
                    </DialogHeader>
                    {created && (
                        <div className="space-y-4 min-w-0">
                            <div className="flex items-center gap-2">
                                <Input readOnly value={created.key} className="font-mono text-xs" aria-label="New API key" />
                                <CopyButton value={created.key} label="Copy API key" />
                            </div>
                            <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-medium text-muted-foreground">MCP client configuration</span>
                                    <CopyButton value={mcpClientConfig(created.key)} label="Copy MCP client configuration" />
                                </div>
                                <pre className="max-h-56 overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs">
                                    {mcpClientConfig(created.key)}
                                </pre>
                            </div>
                        </div>
                    )}
                    <DialogFooter>
                        <Button onClick={() => setCreated(null)}>Done</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    );
}
