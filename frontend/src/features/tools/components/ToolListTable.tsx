"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ToolRead } from "@/types";
import { HealthBadge } from "@/components/common/HealthBadge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Play, ExternalLink, Eye, Copy, Check, Server, FileText } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { toast } from "sonner";

interface ToolListTableProps {
    tools: ToolRead[];
}

export function ToolListTable({ tools }: ToolListTableProps) {
    const [previewTool, setPreviewTool] = useState<ToolRead | null>(null);
    const [copiedId, setCopiedId] = useState<string | null>(null);

    const handleCopyId = (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        e.preventDefault();
        navigator.clipboard.writeText(id);
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 2000);
        toast.success("Tool ID copied to clipboard");
    };

    const handleCopySchema = (tool: ToolRead) => {
        navigator.clipboard.writeText(JSON.stringify(tool.input_schema, null, 2));
        toast.success("JSON Schema copied to clipboard");
    };

    return (
        <>
            <div className="rounded-md border border-border bg-card">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Tool Name</TableHead>
                            <TableHead>Server</TableHead>
                            <TableHead>Description</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead>Parameters</TableHead>
                            <TableHead>Last Discovered</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {tools.map((tool) => {
                            const properties = tool.input_schema?.properties || {};
                            const requiredCount = tool.input_schema?.required?.length || 0;
                            const propKeys = Object.keys(properties);

                            return (
                                <TableRow key={tool.id} className="group">
                                    <TableCell className="font-medium">
                                        <div className="flex flex-col">
                                            <Link
                                                href={`/tools/${encodeURIComponent(tool.id)}`}
                                                className="font-mono font-semibold text-foreground hover:text-primary transition-colors flex items-center gap-1.5"
                                            >
                                                {tool.name}
                                                <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                                            </Link>
                                            <div className="flex items-center gap-1 mt-0.5">
                                                <span className="text-[11px] font-mono text-muted-foreground truncate max-w-[180px]">
                                                    {tool.id}
                                                </span>
                                                <button
                                                    type="button"
                                                    onClick={(e) => handleCopyId(e, tool.id)}
                                                    className="text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 transition-opacity"
                                                    title="Copy qualified ID"
                                                >
                                                    {copiedId === tool.id ? (
                                                        <Check className="h-3 w-3 text-emerald-500" />
                                                    ) : (
                                                        <Copy className="h-3 w-3" />
                                                    )}
                                                </button>
                                            </div>
                                        </div>
                                    </TableCell>

                                    <TableCell>
                                        <div className="flex items-center gap-1.5">
                                            <Server className="h-3 w-3 text-muted-foreground" />
                                            <Link
                                                href={`/servers/${tool.server_id}`}
                                                className="inline-flex items-center text-xs font-medium text-foreground hover:underline"
                                            >
                                                {tool.server_name}
                                            </Link>
                                        </div>
                                    </TableCell>

                                    <TableCell className="text-xs text-muted-foreground max-w-sm">
                                        <p className="line-clamp-2">{tool.description || "No description"}</p>
                                    </TableCell>

                                    <TableCell>
                                        <HealthBadge status={tool.availability_status} />
                                    </TableCell>

                                    <TableCell>
                                        <span className="inline-flex items-center text-xs font-mono bg-muted/70 px-2 py-0.5 rounded">
                                            {propKeys.length} param
                                            {propKeys.length === 1 ? "" : "s"}
                                            {requiredCount > 0 && ` (${requiredCount} req)`}
                                        </span>
                                    </TableCell>

                                    <TableCell className="text-xs text-muted-foreground">{formatDate(tool.last_discovered_at)}</TableCell>

                                    <TableCell className="text-right">
                                        <div className="flex items-center justify-end gap-1.5">
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                className="h-8 w-8 p-0"
                                                title="Quick Schema Preview"
                                                onClick={() => setPreviewTool(tool)}
                                            >
                                                <Eye className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
                                                <span className="sr-only">Quick View</span>
                                            </Button>

                                            <Button asChild size="sm" variant="outline" className="h-8 gap-1.5">
                                                <Link href={`/playground?server=${tool.server_id}&tool=${encodeURIComponent(tool.name)}`}>
                                                    <Play className="h-3.5 w-3.5 text-primary" />
                                                    Test
                                                </Link>
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </div>

            {/* Quick Schema Preview Dialog */}
            <Dialog open={Boolean(previewTool)} onOpenChange={(open) => !open && setPreviewTool(null)}>
                <DialogContent className="max-w-xl max-h-[85vh] flex flex-col">
                    <DialogHeader>
                        <div className="flex items-center justify-between pr-4">
                            <DialogTitle className="font-mono flex items-center gap-2">
                                <FileText className="h-4 w-4 text-primary" />
                                {previewTool?.name}
                            </DialogTitle>
                            {previewTool && <HealthBadge status={previewTool.availability_status} />}
                        </div>
                        <DialogDescription>
                            Server: <span className="font-semibold text-foreground">{previewTool?.server_name}</span> | ID:{" "}
                            <code className="text-xs font-mono bg-muted px-1 py-0.5 rounded">{previewTool?.id}</code>
                        </DialogDescription>
                    </DialogHeader>

                    {previewTool && (
                        <div className="space-y-4 overflow-y-auto pr-1 py-2">
                            {previewTool.description && (
                                <div className="text-xs text-muted-foreground rounded bg-muted/40 p-2.5 border border-border">
                                    {previewTool.description}
                                </div>
                            )}

                            <div>
                                <div className="flex items-center justify-between mb-2">
                                    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                        Parameters ({Object.keys(previewTool.input_schema?.properties || {}).length})
                                    </h4>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => handleCopySchema(previewTool)}
                                        className="h-6 text-xs gap-1"
                                    >
                                        <Copy className="h-3 w-3" />
                                        Copy Schema
                                    </Button>
                                </div>

                                {Object.keys(previewTool.input_schema?.properties || {}).length === 0 ? (
                                    <p className="text-xs text-muted-foreground italic">No input parameters required.</p>
                                ) : (
                                    <div className="rounded-md border border-border overflow-hidden">
                                        <table className="w-full text-xs">
                                            <thead className="bg-muted/50 border-b border-border">
                                                <tr>
                                                    <th className="p-2 text-left font-medium">Field</th>
                                                    <th className="p-2 text-left font-medium">Type</th>
                                                    <th className="p-2 text-left font-medium">Required</th>
                                                    <th className="p-2 text-left font-medium">Description</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-border">
                                                {Object.entries(previewTool.input_schema?.properties || {}).map(
                                                    ([key, prop]: [string, any]) => {
                                                        const isReq = (previewTool.input_schema?.required || []).includes(key);
                                                        return (
                                                            <tr key={key} className="hover:bg-muted/20">
                                                                <td className="p-2 font-mono font-semibold">{key}</td>
                                                                <td className="p-2 font-mono text-muted-foreground">
                                                                    {prop.type || "any"}
                                                                </td>
                                                                <td className="p-2">
                                                                    {isReq ? (
                                                                        <span className="font-semibold text-destructive">Yes</span>
                                                                    ) : (
                                                                        <span className="text-muted-foreground">No</span>
                                                                    )}
                                                                </td>
                                                                <td className="p-2 text-muted-foreground max-w-xs">
                                                                    {prop.description || "-"}
                                                                </td>
                                                            </tr>
                                                        );
                                                    }
                                                )}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    <DialogFooter className="gap-2 sm:gap-0">
                        {previewTool && (
                            <>
                                <Button asChild variant="outline" size="sm">
                                    <Link href={`/tools/${encodeURIComponent(previewTool.id)}`}>
                                        <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                                        Full Details
                                    </Link>
                                </Button>
                                <Button asChild size="sm">
                                    <Link href={`/playground?server=${previewTool.server_id}&tool=${encodeURIComponent(previewTool.name)}`}>
                                        <Play className="mr-1.5 h-3.5 w-3.5" />
                                        Test in Playground
                                    </Link>
                                </Button>
                            </>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
