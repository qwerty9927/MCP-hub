"use client";

import React, { useEffect, useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { History, Loader2, Search, Server, Wrench, Clock, LucideIcon } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { executionsApi, serversApi, toolsApi } from "@/lib/api";
import { useRecents } from "@/lib/recents";
import { cn, formatDate } from "@/lib/utils";

const RESULTS_PER_GROUP = 5;
const DEBOUNCE_MS = 250;

export interface SearchResult {
    id: string;
    group: string;
    label: string;
    detail?: string;
    href: string;
    icon: LucideIcon;
}

interface QuickSearchDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

function useDebounced(value: string, delay: number): string {
    const [debounced, setDebounced] = useState(value);
    useEffect(() => {
        const timer = setTimeout(() => setDebounced(value), delay);
        return () => clearTimeout(timer);
    }, [value, delay]);
    return debounced;
}

/**
 * Quick search across servers, tools and executions (⌘K). The backend has no single search endpoint, so it fans
 * out to each list's own filter: servers and tools by name/description, executions by tool name.
 * With an empty query it offers the recent pages.
 */
export function QuickSearchDialog({ open, onOpenChange }: QuickSearchDialogProps) {
    const router = useRouter();
    const listId = useId();
    const [query, setQuery] = useState("");
    const [active, setActive] = useState(0);
    const term = useDebounced(query.trim(), DEBOUNCE_MS);
    const searching = term.length > 0;
    const recents = useRecents();

    const { data: results = [], isFetching } = useQuery({
        queryKey: ["quick-search", term],
        enabled: open && searching,
        staleTime: 10_000,
        queryFn: async ({ signal }): Promise<SearchResult[]> => {
            const [servers, tools, executions] = await Promise.allSettled([
                serversApi.list({ search: term, page: 1, page_size: RESULTS_PER_GROUP }, signal),
                toolsApi.list({ search: term, page: 1, page_size: RESULTS_PER_GROUP }, signal),
                executionsApi.list({ tool_name: term, page: 1, page_size: RESULTS_PER_GROUP }, signal),
            ]);
            return [
                ...(servers.status === "fulfilled" ? servers.value.items : []).map((server) => ({
                    id: `server-${server.id}`,
                    group: "Servers",
                    label: server.name,
                    detail: `${server.transport} · ${server.discovered_tool_count} tools`,
                    href: `/servers/${server.id}`,
                    icon: Server,
                })),
                ...(tools.status === "fulfilled" ? tools.value.items : []).map((tool) => ({
                    id: `tool-${tool.id}`,
                    group: "Tools",
                    label: tool.name,
                    detail: tool.server_name,
                    href: `/tools/${encodeURIComponent(tool.id)}`,
                    icon: Wrench,
                })),
                ...(executions.status === "fulfilled" ? executions.value.items : []).map((execution) => ({
                    id: `execution-${execution.id}`,
                    group: "Executions",
                    label: execution.tool_name,
                    detail: `${execution.server_name} · ${formatDate(execution.executed_at)}`,
                    href: `/executions/${execution.id}`,
                    icon: History,
                })),
            ];
        },
    });

    const items: SearchResult[] = useMemo(
        () =>
            searching
                ? results
                : recents.map((recent) => ({
                      id: `recent-${recent.href}`,
                      group: "Recent",
                      label: recent.label,
                      detail: recent.section,
                      href: recent.href,
                      icon: Clock,
                  })),
        [searching, results, recents]
    );
    const current = Math.min(active, Math.max(items.length - 1, 0));
    const groups = useMemo(() => Array.from(new Set(items.map((item) => item.group))), [items]);

    const handleOpenChange = (next: boolean) => {
        if (!next) {
            setQuery("");
            setActive(0);
        }
        onOpenChange(next);
    };

    const go = (item: SearchResult | undefined) => {
        if (!item) return;
        handleOpenChange(false);
        router.push(item.href);
    };

    const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
        if (event.key === "ArrowDown") {
            event.preventDefault();
            setActive(Math.min(current + 1, items.length - 1));
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setActive(Math.max(current - 1, 0));
        } else if (event.key === "Enter") {
            event.preventDefault();
            go(items[current]);
        }
    };

    const optionId = (index: number) => `${listId}-option-${index}`;
    const waiting = searching && (isFetching || query.trim() !== term);

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="top-[15%] max-w-xl translate-y-0 gap-0 p-0">
                <DialogTitle className="sr-only">Quick search</DialogTitle>
                <DialogDescription className="sr-only">
                    Search servers, tools and executions. Use the arrow keys and Enter.
                </DialogDescription>
                <div className="flex items-center gap-2 border-b border-border px-4">
                    <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    <input
                        autoFocus
                        role="combobox"
                        aria-label="Search servers, tools and executions"
                        aria-expanded={items.length > 0}
                        aria-controls={listId}
                        aria-activedescendant={items.length > 0 ? optionId(current) : undefined}
                        aria-autocomplete="list"
                        placeholder="Search servers, tools, executions…"
                        value={query}
                        onChange={(event) => {
                            setQuery(event.target.value);
                            setActive(0);
                        }}
                        onKeyDown={handleKeyDown}
                        className="h-12 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                    />
                    {waiting && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-hidden="true" />}
                </div>

                <div className="max-h-[360px] overflow-y-auto p-2">
                    {items.length === 0 ? (
                        <p className="px-3 py-8 text-center text-sm text-muted-foreground" aria-live="polite">
                            {searching ? (waiting ? "Searching…" : `No results for “${term}”`) : "Type to search. Recent pages show here."}
                        </p>
                    ) : (
                        <ul id={listId} role="listbox" aria-label="Results" className="flex flex-col">
                            {groups.map((group) => (
                                <li key={group} role="presentation">
                                    <span className="block px-3 pb-1 pt-2 text-xs font-medium text-muted-foreground">{group}</span>
                                    <ul role="group" aria-label={group} className="flex flex-col">
                                        {items.map((item, index) => {
                                            if (item.group !== group) return null;
                                            const Icon = item.icon;
                                            const selected = index === current;
                                            return (
                                                <li
                                                    key={item.id}
                                                    id={optionId(index)}
                                                    role="option"
                                                    aria-selected={selected}
                                                    onMouseEnter={() => setActive(index)}
                                                    onClick={() => go(item)}
                                                    className={cn(
                                                        "flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-sm",
                                                        selected ? "bg-accent" : "hover:bg-accent/60"
                                                    )}
                                                >
                                                    <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                                                    <span className="truncate font-medium text-foreground">{item.label}</span>
                                                    {item.detail && (
                                                        <span className="ml-auto truncate pl-3 font-mono text-xs text-muted-foreground">
                                                            {item.detail}
                                                        </span>
                                                    )}
                                                </li>
                                            );
                                        })}
                                    </ul>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}
