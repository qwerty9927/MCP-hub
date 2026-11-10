"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Server, Wrench, Terminal, History, Settings, Cpu, Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { systemApi } from "@/lib/api";

export const NAV_ITEMS = [
    {
        name: "Overview",
        href: "/overview",
        icon: LayoutDashboard,
    },
    {
        name: "MCP Servers",
        href: "/servers",
        icon: Server,
    },
    {
        name: "Tool Catalog",
        href: "/tools",
        icon: Wrench,
    },
    {
        name: "Tool Playground",
        href: "/playground",
        icon: Terminal,
    },
    {
        name: "Sessions",
        href: "/sessions",
        icon: Bot,
    },
    {
        name: "Execution History",
        href: "/executions",
        icon: History,
    },
    {
        name: "Settings",
        href: "/settings",
        icon: Settings,
    },
];

interface SidebarProps {
    onItemClick?: () => void;
    className?: string;
}

export function Sidebar({ onItemClick, className }: SidebarProps) {
    const pathname = usePathname();

    // Polling backend health probe every 30s
    const { data: health, isError } = useQuery({
        queryKey: ["system-health"],
        queryFn: ({ signal }) => systemApi.health(signal),
        refetchInterval: 30000,
        retry: false,
    });

    return (
        <div className={cn("flex h-full flex-col justify-between border-r border-border bg-card/60 backdrop-blur-md px-3 py-4", className)}>
            <div className="space-y-6">
                {/* Brand Header */}
                <div className="flex items-center gap-3 px-3 py-2">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
                        <Cpu className="h-5 w-5" />
                    </div>
                    <div className="flex flex-col">
                        <span className="font-bold text-sm tracking-tight text-foreground">MCP Hub</span>
                        <span className="text-xs text-muted-foreground font-mono">Admin Console</span>
                    </div>
                </div>

                {/* Navigation Items */}
                <nav className="space-y-1">
                    {NAV_ITEMS.map((item) => {
                        const Icon = item.icon;
                        const isActive =
                            item.href === "/overview" ? pathname === "/overview" || pathname === "/" : pathname.startsWith(item.href);

                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                onClick={onItemClick}
                                className={cn(
                                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150",
                                    isActive
                                        ? "bg-primary text-primary-foreground shadow-sm font-semibold"
                                        : "text-muted-foreground hover:bg-muted/80 hover:text-foreground"
                                )}
                            >
                                <Icon className="h-4 w-4 shrink-0" />
                                <span>{item.name}</span>
                            </Link>
                        );
                    })}
                </nav>
            </div>

            {/* Backend Status Footer */}
            <div className="rounded-lg border border-border bg-muted/40 p-3 text-xs">
                <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Backend API</span>
                    <span className="flex items-center gap-1.5 font-medium">
                        <span className={cn("h-2 w-2 rounded-full", isError ? "bg-red-500" : health ? "bg-emerald-500" : "bg-amber-500")} />
                        {isError ? "Offline" : health ? "Online" : "Connecting"}
                    </span>
                </div>
                {health && <div className="mt-1 text-[11px] text-muted-foreground font-mono">v{health.version}</div>}
            </div>
        </div>
    );
}
