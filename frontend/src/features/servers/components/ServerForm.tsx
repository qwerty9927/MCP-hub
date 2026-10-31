"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ServerRead } from "@/types";
import { serverFormSchema, ServerFormValues } from "@/schemas/server.schema";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Terminal, Globe, AlertCircle, Loader2 } from "lucide-react";

interface ServerFormProps {
    initialData?: ServerRead;
    onSubmit: (values: any) => Promise<void>;
    isLoading: boolean;
    onCancel?: () => void;
}

export function ServerForm({ initialData, onSubmit, isLoading, onCancel }: ServerFormProps) {
    const isEdit = Boolean(initialData);

    // Parse initial env & headers if available
    const initialArgs = initialData?.connection_config.args?.join(" ") || "";
    const initialHeaders = initialData?.connection_config.headers
        ? JSON.stringify(initialData.connection_config.headers, null, 2)
        : "";

    const {
        register,
        handleSubmit,
        setValue,
        setError,
        watch,
        formState: { errors },
    } = useForm<ServerFormValues>({
        resolver: zodResolver(serverFormSchema) as any,
        defaultValues: {
            name: initialData?.name || "",
            description: initialData?.description || "",
            transport: initialData?.transport || "stdio",
            enabled: initialData ? initialData.enabled : true,
            stdio_command: initialData?.connection_config.command || "",
            stdio_args: initialArgs,
            stdio_env: "",
            http_url: initialData?.connection_config.url || "",
            http_headers: initialHeaders,
        },
    });

    const selectedTransport = watch("transport");
    const isEnabled = watch("enabled");

    const [formError, setFormError] = useState<string | null>(null);

    const onFormSubmit = async (data: ServerFormValues) => {
        setFormError(null);
        try {
            const payload: any = {
                name: data.name.trim(),
                description: data.description ? data.description.trim() : null,
                transport: data.transport,
                enabled: data.enabled,
            };

            if (data.transport === "stdio") {
                // Parse args into array
                const argsArray = data.stdio_args
                    ? data.stdio_args.trim().split(/\s+/).filter(Boolean)
                    : [];

                // Parse env if provided
                let envObj: Record<string, string> = {};
                if (data.stdio_env && data.stdio_env.trim()) {
                    try {
                        envObj = JSON.parse(data.stdio_env);
                    } catch {
                        // Parse KEY=VALUE lines
                        data.stdio_env.split("\n").forEach((line) => {
                            const [k, ...v] = line.split("=");
                            if (k && v.length) {
                                envObj[k.trim()] = v.join("=").trim();
                            }
                        });
                    }
                }

                payload.stdio_config = {
                    command: data.stdio_command!.trim(),
                    args: argsArray,
                    env: envObj,
                };
            } else if (data.transport === "streamable-http") {
                let headersObj: Record<string, string> = {};
                if (data.http_headers && data.http_headers.trim()) {
                    try {
                        headersObj = JSON.parse(data.http_headers);
                    } catch {
                        // Parse Key: Value lines
                        data.http_headers.split("\n").forEach((line) => {
                            const [k, ...v] = line.split(":");
                            if (k && v.length) {
                                headersObj[k.trim()] = v.join(":").trim();
                            }
                        });
                    }
                }

                payload.http_config = {
                    url: data.http_url!.trim(),
                    headers: headersObj,
                };
            }

            await onSubmit(payload);
        } catch (err: any) {
            if (err?.details && Array.isArray(err.details)) {
                err.details.forEach((item: any) => {
                    const loc = item.loc || [];
                    const field = loc[loc.length - 1];
                    if (field === "name") {
                        setError("name", { message: item.msg });
                    } else if (field === "command" || field === "stdio_config") {
                        setError("stdio_command", { message: item.msg });
                    } else if (field === "url" || field === "http_config") {
                        setError("http_url", { message: item.msg });
                    } else if (field === "description") {
                        setError("description", { message: item.msg });
                    }
                });
            }
            setFormError(err.message || "An error occurred while saving the server");
        }
    };

    return (
        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-6">
            {formError && (
                <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>{formError}</span>
                </div>
            )}

            {/* General Settings */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Server Information</CardTitle>
                    <CardDescription>
                        Basic metadata and communication configuration for this MCP server.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="name">Server Name *</Label>
                        <Input
                            id="name"
                            placeholder="e.g. math-tools-service"
                            disabled={isLoading || isEdit}
                            {...register("name")}
                        />
                        {errors.name && (
                            <p className="text-xs text-destructive">{errors.name.message}</p>
                        )}
                        <p className="text-xs text-muted-foreground">
                            Unique identifier for this server instance.
                        </p>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="description">Description</Label>
                        <Textarea
                            id="description"
                            placeholder="e.g. Provides mathematical calculation and scientific formula tools"
                            rows={3}
                            disabled={isLoading}
                            {...register("description")}
                        />
                        {errors.description && (
                            <p className="text-xs text-destructive">{errors.description.message}</p>
                        )}
                    </div>

                    <div className="flex items-center justify-between rounded-lg border border-border p-3 shadow-sm">
                        <div className="space-y-0.5">
                            <Label htmlFor="enabled">Enabled for Execution</Label>
                            <p className="text-xs text-muted-foreground">
                                When disabled, tools registered with this server cannot be invoked.
                            </p>
                        </div>
                        <Switch
                            id="enabled"
                            checked={isEnabled}
                            onCheckedChange={(checked) => setValue("enabled", checked)}
                            disabled={isLoading}
                        />
                    </div>
                </CardContent>
            </Card>

            {/* Transport Configuration */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Transport Protocol</CardTitle>
                    <CardDescription>
                        Choose between local subprocess (stdio) or remote streamable HTTP server.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="transport">Transport Type *</Label>
                        <Select
                            value={selectedTransport}
                            onValueChange={(val: any) => setValue("transport", val)}
                            disabled={isLoading || isEdit}
                        >
                            <SelectTrigger id="transport">
                                <SelectValue placeholder="Select transport" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="stdio">
                                    <div className="flex items-center gap-2">
                                        <Terminal className="h-4 w-4 text-primary" />
                                        <span>stdio (Local Subprocess)</span>
                                    </div>
                                </SelectItem>
                                <SelectItem value="streamable-http">
                                    <div className="flex items-center gap-2">
                                        <Globe className="h-4 w-4 text-emerald-500" />
                                        <span>streamable-http (Remote HTTP Server)</span>
                                    </div>
                                </SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Conditional stdio Configuration */}
                    {selectedTransport === "stdio" && (
                        <div className="space-y-4 rounded-lg border border-border/80 bg-muted/20 p-4">
                            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                                <Terminal className="h-4 w-4 text-primary" />
                                <span>Local Subprocess (stdio) Configuration</span>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="stdio_command">Command / Executable *</Label>
                                <Input
                                    id="stdio_command"
                                    placeholder="e.g. python3, node, uvx"
                                    disabled={isLoading}
                                    {...register("stdio_command")}
                                />
                                {errors.stdio_command && (
                                    <p className="text-xs text-destructive">
                                        {errors.stdio_command.message}
                                    </p>
                                )}
                                <p className="text-xs text-muted-foreground">
                                    The executable name or binary path allowed by backend security
                                    policies.
                                </p>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="stdio_args">Arguments</Label>
                                <Input
                                    id="stdio_args"
                                    placeholder="e.g. -m demo_server.server"
                                    disabled={isLoading}
                                    {...register("stdio_args")}
                                />
                                {errors.stdio_args && (
                                    <p className="text-xs text-destructive">
                                        {errors.stdio_args.message}
                                    </p>
                                )}
                                <p className="text-xs text-muted-foreground">
                                    Space-delimited command arguments.
                                </p>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="stdio_env">
                                    Environment Variables (JSON or KEY=VAL)
                                </Label>
                                <Textarea
                                    id="stdio_env"
                                    placeholder={`{"CALC_PRECISION": "4"}`}
                                    rows={3}
                                    className="font-mono text-xs"
                                    disabled={isLoading}
                                    {...register("stdio_env")}
                                />
                                {errors.stdio_env && (
                                    <p className="text-xs text-destructive">
                                        {errors.stdio_env.message}
                                    </p>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Conditional HTTP Configuration */}
                    {selectedTransport === "streamable-http" && (
                        <div className="space-y-4 rounded-lg border border-border/80 bg-muted/20 p-4">
                            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                                <Globe className="h-4 w-4 text-emerald-500" />
                                <span>Streamable HTTP Configuration</span>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="http_url">Endpoint URL *</Label>
                                <Input
                                    id="http_url"
                                    type="url"
                                    placeholder="https://mcp.internal.example.com/mcp"
                                    disabled={isLoading}
                                    {...register("http_url")}
                                />
                                {errors.http_url && (
                                    <p className="text-xs text-destructive">
                                        {errors.http_url.message}
                                    </p>
                                )}
                                <p className="text-xs text-muted-foreground">
                                    Target MCP streamable HTTP URL. Must be http:// or https://.
                                </p>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="http_headers">
                                    Request Headers (JSON or Header: Value)
                                </Label>
                                <Textarea
                                    id="http_headers"
                                    placeholder={`{\n  "Authorization": "Bearer secret-token"\n}`}
                                    rows={4}
                                    className="font-mono text-xs"
                                    disabled={isLoading}
                                    {...register("http_headers")}
                                />
                                {errors.http_headers && (
                                    <p className="text-xs text-destructive">
                                        {errors.http_headers.message}
                                    </p>
                                )}
                                <p className="text-xs text-muted-foreground">
                                    Sensitive authorization headers are safely masked by the
                                    backend.
                                </p>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-3 pt-2">
                {onCancel && (
                    <Button type="button" variant="outline" disabled={isLoading} onClick={onCancel}>
                        Cancel
                    </Button>
                )}
                <Button type="submit" disabled={isLoading} className="gap-2">
                    {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
                    {isEdit ? "Update Server" : "Register Server"}
                </Button>
            </div>
        </form>
    );
}
