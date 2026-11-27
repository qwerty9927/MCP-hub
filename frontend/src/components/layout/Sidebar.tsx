"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    LayoutDashboard,
    Server,
    Wrench,
    Terminal,
    History,
    BarChart3,
    Settings,
    Cpu,
    Bot,
    Compass,
    KeyRound,
    Search,
    ChevronsUpDown,
    ChevronRight,
    ChevronDown,
    LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { serversApi, systemApi } from "@/lib/api";
import { API_BASE_URL, SHOW_BACKEND_DETAILS } from "@/lib/config";
import { SERVERS_QUERY_KEY } from "@/features/servers/hooks/use-servers";
import { PendingBadge } from "@/components/common/PendingBackend";
import { ServerFilterParams } from "@/types";

export interface NavItem {
    name: string;
    href: string;
    icon: LucideIcon;
}

export interface NavGroup {
    /** Quiet section label; null for the ungrouped top items. */
    label: string | null;
    items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
    { label: null, items: [{ name: "Overview", href: "/overview", icon: LayoutDashboard }] },
    {
        label: "Registry",
        items: [
            { name: "MCP Servers", href: "/servers", icon: Server },
            { name: "Tool Catalog", href: "/tools", icon: Wrench },
            { name: "Discovery", href: "/discovery", icon: Compass },
        ],
    },
    {
        label: "Operate",
        items: [
            { name: "Tool Playground", href: "/playground", icon: Terminal },
            { name: "Sessions", href: "/sessions", icon: Bot },
            { name: "Execution History", href: "/executions", icon: History },
            { name: "Metrics", href: "/metrics", icon: BarChart3 },
        ],
    },
    {
        label: "Manage",
        items: [
            { name: "API Keys", href: "/settings/api-keys", icon: KeyRound },
            { name: "Settings", href: "/settings", icon: Settings },
        ],
    },
];

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);

/** The nav item for a path: the longest href that is the path or a parent of it ("/" counts as Overview). */
export function activeNavHref(pathname: string): string | null {
    if (pathname === "/") return "/overview";
    const matches = NAV_ITEMS.filter((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
    return matches.sort((a, b) => b.href.length - a.href.length)[0]?.href ?? null;
}

/** First servers by name, listed under MCP Servers while a server page is open. */
const SERVER_SUBLIST_PARAMS: ServerFilterParams = { page: 1, page_size: 6, sort_by: "name", sort_order: "asc" };

/** host:port of the backend, shown under the hub name outside production builds. */
function backendHost(): string {
    try {
        return new URL(API_BASE_URL).host;
    } catch {
        return API_BASE_URL;
    }
}

interface SidebarProps {
    onItemClick?: () => void;
    /** Opens quick search (⌘K). */
    onOpenSearch?: () => void;
    className?: string;
}

export function Sidebar({ onItemClick, onOpenSearch, className }: SidebarProps) {
    const pathname = usePathname();
    const activeHref = activeNavHref(pathname);
    const inServers = activeHref === "/servers";

    // Backend status footer: polls /health every 30s and times the round trip.
    const { data: health, isError } = useQuery({
        queryKey: ["system-health", "timed"],
        queryFn: async ({ signal }) => {
            const started = performance.now();
            const result = await systemApi.health(signal);
            return { ...result, latencyMs: Math.round(performance.now() - started) };
        },
        refetchInterval: 30000,
        retry: false,
    });

    const { data: serverList } = useQuery({
        queryKey: [...SERVERS_QUERY_KEY, SERVER_SUBLIST_PARAMS],
        queryFn: ({ signal }) => serversApi.list(SERVER_SUBLIST_PARAMS, signal),
        enabled: inServers,
    });

    return (
        <div className={cn("flex h-full flex-col gap-3 overflow-y-auto border-r border-border bg-background px-3 py-3", className)}>
            {/* Hub identity; switching hubs is pending in the backend */}
            <div className="flex items-center gap-2.5 rounded-lg px-2 py-1.5">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
                    <Cpu className="h-4 w-4" aria-hidden="true" />
                </div>
                <div className="flex min-w-0 flex-1 flex-col">
                    <span className="text-sm font-semibold leading-[18px] text-foreground">MCP Hub</span>
                    <span className="truncate font-mono text-xs text-muted-foreground">
                        {SHOW_BACKEND_DETAILS ? backendHost() : "Admin Console"}
                    </span>
                </div>
                <PendingBadge id="hub-switcher" icon={ChevronsUpDown} />
            </div>

            {/* Quick search */}
            <button
                type="button"
                onClick={onOpenSearch}
                className="flex h-9 shrink-0 items-center gap-2 rounded-md border border-input px-2.5 text-[13px] text-muted-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
                <Search className="h-3.5 w-3.5" aria-hidden="true" />
                <span className="flex-1 text-left">Quick search…</span>
                <kbd className="rounded border border-border px-1.5 font-mono text-[11px] leading-4">⌘K</kbd>
            </button>

            <nav aria-label="Main" className="flex flex-col gap-0.5">
                {NAV_GROUPS.map((group) => (
                    <React.Fragment key={group.label ?? "top"}>
                        {group.label && <span className="px-2.5 pb-1 pt-3.5 text-xs font-medium text-muted-foreground">{group.label}</span>}
                        {group.items.map((item) => {
                            const Icon = item.icon;
                            const expandable = item.href === "/servers";
                            // On a server page the server row is highlighted, not MCP Servers itself.
                            const isActive = activeHref === item.href && !(expandable && pathname !== "/servers");
                            return (
                                <React.Fragment key={item.href}>
                                    <Link
                                        href={item.href}
                                        onClick={onItemClick}
                                        aria-current={isActive ? "page" : undefined}
                                        className={cn(
                                            "flex min-h-9 items-center gap-2.5 rounded-md px-2.5 text-sm transition-colors",
                                            isActive
                                                ? "bg-accent font-semibold text-primary"
                                                : "font-medium text-foreground hover:bg-accent"
                                        )}
                                    >
                                        <Icon
                                            className={cn("h-4 w-4 shrink-0", isActive ? "text-primary" : "text-muted-foreground")}
                                            aria-hidden="true"
                                        />
                                        <span className="flex-1">{item.name}</span>
                                        {expandable &&
                                            (inServers ? (
                                                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                                            ) : (
                                                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                                            ))}
                                    </Link>
                                    {expandable && inServers && serverList && serverList.items.length > 0 && (
                                        <div className="ml-[18px] flex flex-col gap-0.5 border-l border-border pl-2.5">
                                            {serverList.items.map((server) => {
                                                const href = `/servers/${server.id}`;
                                                const current = pathname === href || pathname.startsWith(`${href}/`);
                                                return (
                                                    <Link
                                                        key={server.id}
                                                        href={href}
                                                        onClick={onItemClick}
                                                        aria-current={current ? "page" : undefined}
                                                        className={cn(
                                                            "flex min-h-8 items-center rounded-md px-2.5 text-[13px] transition-colors",
                                                            current
                                                                ? "bg-accent font-semibold text-primary"
                                                                : "text-foreground hover:bg-accent"
                                                        )}
                                                    >
                                                        <span className="truncate">{server.name}</span>
                                                    </Link>
                                                );
                                            })}
                                            {serverList.total > serverList.items.length && (
                                                <Link
                                                    href="/servers"
                                                    onClick={onItemClick}
                                                    className="flex min-h-8 items-center rounded-md px-2.5 text-[13px] text-muted-foreground hover:bg-accent"
                                                >
                                                    All {serverList.total} servers
                                                </Link>
                                            )}
                                        </div>
                                    )}
                                </React.Fragment>
                            );
                        })}
                    </React.Fragment>
                ))}
            </nav>

            {/* Backend status (the version and latency are hidden in production builds) */}
            <div className="mt-auto rounded-lg border border-border p-3 text-xs">
                <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Backend API</span>
                    <span className="flex items-center gap-1.5 font-medium">
                        <span
                            aria-hidden="true"
                            className={cn("h-2 w-2 rounded-full", isError ? "bg-danger" : health ? "bg-success-dot" : "bg-warning")}
                        />
                        {isError ? "Offline" : health ? "Online" : "Connecting"}
                    </span>
                </div>
                {SHOW_BACKEND_DETAILS && health && (
                    <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                        <span>v{health.version}</span>
                        <span> · {health.latencyMs}ms</span>
                    </div>
                )}
            </div>
        </div>
    );
}
