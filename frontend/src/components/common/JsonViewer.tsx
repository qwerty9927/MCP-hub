"use client";

import React, { useState } from "react";
import JsonView from "@uiw/react-json-view";
import { vscodeTheme } from "@uiw/react-json-view/vscode";
import { githubLightTheme } from "@uiw/react-json-view/githubLight";
import { useTheme } from "next-themes";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToolContentItem } from "@/types";
import { cn } from "@/lib/utils";

const BOX = "rounded-lg border border-border bg-muted/60 p-3.5 font-mono text-xs overflow-auto";

/** The parsed value when `text` is a JSON object or array, otherwise null (plain text, numbers and broken JSON stay text). */
export function parseJsonText(text: string): object | null {
    try {
        const value: unknown = JSON.parse(text);
        return typeof value === "object" && value !== null ? value : null;
    } catch {
        return null;
    }
}

interface JsonViewerProps {
    value: unknown;
    /** Depth at which nodes start collapsed. */
    collapsed?: number;
    className?: string;
}

/** Collapsible JSON tree that follows the app theme; values that are not objects or arrays show as plain text. */
export function JsonViewer({ value, collapsed = 2, className }: JsonViewerProps) {
    const { resolvedTheme } = useTheme();

    if (typeof value !== "object" || value === null) {
        return <pre className={cn(BOX, className)}>{JSON.stringify(value, null, 2)}</pre>;
    }

    const theme = {
        ...(resolvedTheme === "dark" ? vscodeTheme : githubLightTheme),
        "--w-rjv-background-color": "transparent",
        "--w-rjv-font-family": "inherit",
    } as React.CSSProperties;

    return (
        <div className={cn(BOX, className)}>
            <JsonView value={value} style={theme} collapsed={collapsed} displayDataTypes={false} shortenTextAfterLength={160} />
        </div>
    );
}

/** One MCP content block: text holding JSON renders as a tree, other text as text, and non-text blocks as a tree. */
export function ContentBlock({ item, className }: { item: ToolContentItem; className?: string }) {
    if (item.text) {
        const parsed = parseJsonText(item.text);
        if (parsed) return <JsonViewer value={parsed} className={className} />;
        return <div className={cn(BOX, "bg-muted/40 whitespace-pre-wrap break-all", className)}>{item.text}</div>;
    }
    return <JsonViewer value={item} className={className} />;
}

interface JsonTabsProps {
    /** Content of the Formatted tab. */
    formatted: React.ReactNode;
    /** Value shown pretty-printed in the Raw JSON tab. */
    raw: unknown;
    /** Height limit for the raw view, e.g. "max-h-[300px]". */
    rawClassName?: string;
    className?: string;
}

/** Formatted / Raw JSON tab pair; the raw tab is the pretty-printed JSON text. */
export function JsonTabs({ formatted, raw, rawClassName, className }: JsonTabsProps) {
    const [tab, setTab] = useState<"formatted" | "raw">("formatted");

    return (
        <Tabs value={tab} onValueChange={(v) => setTab(v as "formatted" | "raw")} className={className}>
            <TabsList className="h-7 max-w-[200px] grid grid-cols-2 mb-3">
                <TabsTrigger value="formatted" onClick={() => setTab("formatted")} className="text-xs h-6">
                    Formatted
                </TabsTrigger>
                <TabsTrigger value="raw" onClick={() => setTab("raw")} className="text-xs h-6">
                    Raw JSON
                </TabsTrigger>
            </TabsList>

            <TabsContent value="formatted" className="space-y-2 mt-0">
                {formatted}
            </TabsContent>

            <TabsContent value="raw" className="mt-0">
                <pre className={cn(BOX, rawClassName)}>{JSON.stringify(raw, null, 2)}</pre>
            </TabsContent>
        </Tabs>
    );
}
