"use client";

import React, { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Plug } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SearchInput } from "@/components/common/SearchInput";
import { cn } from "@/lib/utils";
import { OAuthProvider } from "@/types";
import { useServer } from "../hooks/use-servers";
import { useOAuthFlow, useOAuthProviders } from "../hooks/use-oauth";
import { ProviderCard, providerHost } from "./ProviderCard";
import { OAuthConnectPanel } from "./OAuthConnectPanel";

/** Where "Configure manually" goes: the full-page form, kept outside the dialog. */
export const MANUAL_REGISTER_PATH = "/servers/new";

export type RegisterServerStep = "providers" | "connecting";

interface RegisterServerDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

/** Providers whose name, description, category or host contains the query (case-insensitive), in one category. */
export function filterProviders(providers: OAuthProvider[], query: string, category: string | null): OAuthProvider[] {
    const needle = query.trim().toLowerCase();
    return providers.filter(
        (provider) =>
            (!category || provider.category === category) &&
            (!needle ||
                [provider.name, provider.description, provider.category, providerHost(provider.mcp_url)].some((value) =>
                    value.toLowerCase().includes(needle)
                ))
    );
}

function gridColumns(): number {
    return typeof window !== "undefined" && window.matchMedia?.("(min-width: 640px)").matches ? 2 : 1;
}

/**
 * Register Server: pick a hosted provider and sign in through a popup.
 * Steps: providers (search + category chips) → connecting (popup, then done / error).
 * "Configure manually" closes the dialog and opens the full-page form at /servers/new.
 */
export function RegisterServerDialog({ open, onOpenChange }: RegisterServerDialogProps) {
    const router = useRouter();
    const [step, setStep] = useState<RegisterServerStep>("providers");
    const [query, setQuery] = useState("");
    const [category, setCategory] = useState<string | null>(null);
    const [selected, setSelected] = useState<OAuthProvider | null>(null);
    const [activeIndex, setActiveIndex] = useState(0);
    const searchRef = useRef<HTMLInputElement>(null);
    const cardRefs = useRef<(HTMLButtonElement | null)[]>([]);

    const providersQuery = useOAuthProviders(open);
    const flow = useOAuthFlow();
    const connectedServerId = flow.state.status === "success" ? (flow.state.serverId ?? "") : "";
    const { data: connectedServer } = useServer(connectedServerId);

    const providers = useMemo(() => providersQuery.data ?? [], [providersQuery.data]);
    const categories = useMemo(() => Array.from(new Set(providers.map((provider) => provider.category))), [providers]);
    const filtered = useMemo(() => filterProviders(providers, query, category), [providers, query, category]);
    const current = Math.min(activeIndex, Math.max(filtered.length - 1, 0));

    const resetAll = () => {
        flow.reset();
        setStep("providers");
        setQuery("");
        setCategory(null);
        setSelected(null);
        setActiveIndex(0);
    };

    const handleOpenChange = (next: boolean) => {
        if (!next) resetAll();
        onOpenChange(next);
    };

    const backToProviders = () => {
        flow.reset();
        setStep("providers");
        // Wait for the providers step to render before focusing its search box.
        requestAnimationFrame(() => searchRef.current?.focus());
    };

    const goManual = () => {
        handleOpenChange(false);
        router.push(MANUAL_REGISTER_PATH);
    };

    const connect = (provider: OAuthProvider) => {
        if (!provider.available) return;
        setSelected(provider);
        setStep("connecting");
        // A second connection to the same provider gets a numbered name so the two servers are told apart.
        const name = provider.connected_count > 0 ? `${provider.name} ${provider.connected_count + 1}` : undefined;
        void flow.connect(name ? { provider_id: provider.id, name } : { provider_id: provider.id });
    };

    const openServer = (serverId: string) => {
        handleOpenChange(false);
        router.push(`/servers/${serverId}`);
    };

    const focusCard = (index: number) => {
        const next = Math.max(0, Math.min(index, filtered.length - 1));
        setActiveIndex(next);
        cardRefs.current[next]?.focus();
    };

    // Roving tabindex over the grid: arrows move by one card (left/right) or one row (up/down).
    const handleGridKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
        const columns = gridColumns();
        const moves: Record<string, number> = {
            ArrowRight: current + 1,
            ArrowLeft: current - 1,
            ArrowDown: current + columns,
            ArrowUp: current - columns,
            Home: 0,
            End: filtered.length - 1,
        };
        if (!(event.key in moves)) return;
        event.preventDefault();
        if (event.key === "ArrowUp" && current - columns < 0) {
            searchRef.current?.focus();
            return;
        }
        focusCard(moves[event.key]);
    };

    const handleSearchKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
        if (event.key === "ArrowDown" && filtered.length > 0) {
            event.preventDefault();
            focusCard(current);
        }
    };

    const description = "Connect a hosted server with your account, or configure one manually.";

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent
                className="flex h-[100dvh] max-w-2xl flex-col gap-0 overflow-hidden rounded-none p-0 sm:h-auto sm:max-h-[85vh] sm:rounded-lg"
                onOpenAutoFocus={(event) => {
                    if (step !== "providers") return;
                    event.preventDefault();
                    searchRef.current?.focus();
                }}
            >
                <DialogHeader className="space-y-3 border-b border-border px-6 pb-4 pt-6 text-left">
                    <div className="space-y-1.5 pr-6">
                        <DialogTitle>Register MCP server</DialogTitle>
                        <DialogDescription>{description}</DialogDescription>
                    </div>

                    {step === "providers" && (
                        <>
                            <SearchInput
                                ref={searchRef}
                                label="Search providers"
                                placeholder="Search providers…"
                                clearLabel="Clear provider search"
                                value={query}
                                onValueChange={(value) => {
                                    setQuery(value);
                                    setActiveIndex(0);
                                }}
                                onKeyDown={handleSearchKeyDown}
                            />
                            {categories.length > 1 && (
                                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by category">
                                    {[null, ...categories].map((value) => {
                                        const active = category === value;
                                        return (
                                            <Button
                                                key={value ?? "all"}
                                                type="button"
                                                size="sm"
                                                variant={active ? "secondary" : "ghost"}
                                                aria-pressed={active}
                                                onClick={() => {
                                                    setCategory(value);
                                                    setActiveIndex(0);
                                                }}
                                                className={cn("h-7 rounded-full px-3", !active && "text-muted-foreground")}
                                            >
                                                {value ?? "All"}
                                            </Button>
                                        );
                                    })}
                                </div>
                            )}
                        </>
                    )}
                </DialogHeader>

                <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
                    {step === "providers" &&
                        (providersQuery.isLoading ? (
                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2" aria-label="Loading providers">
                                {Array.from({ length: 6 }, (_, index) => (
                                    <Skeleton key={index} className="h-[82px] rounded-lg" />
                                ))}
                            </div>
                        ) : providersQuery.isError ? (
                            <div className="flex flex-col items-center gap-3 py-10 text-center">
                                <p className="text-sm text-red-700 dark:text-red-400">
                                    {(providersQuery.error as Error | null)?.message || "Couldn't load the provider list."}
                                </p>
                                <div className="flex gap-2">
                                    <Button variant="outline" onClick={() => providersQuery.refetch()}>
                                        Retry
                                    </Button>
                                    <Button onClick={goManual}>Configure manually</Button>
                                </div>
                            </div>
                        ) : filtered.length === 0 ? (
                            <div className="flex flex-col items-center gap-3 py-10 text-center" data-testid="provider-empty-state">
                                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
                                    <Plug className="h-5 w-5" aria-hidden="true" />
                                </div>
                                <p className="text-sm text-muted-foreground">
                                    {query.trim() ? (
                                        <>
                                            No provider matches &ldquo;<span className="text-foreground">{query.trim()}</span>&rdquo;
                                        </>
                                    ) : (
                                        "No hosted providers are available yet."
                                    )}
                                </p>
                                <Button onClick={goManual}>Configure manually</Button>
                            </div>
                        ) : (
                            <TooltipProvider delayDuration={200}>
                                <div
                                    role="group"
                                    aria-label="Providers"
                                    className="grid grid-cols-1 gap-3 sm:grid-cols-2"
                                    onKeyDown={handleGridKeyDown}
                                >
                                    {filtered.map((provider, index) => (
                                        <ProviderCard
                                            key={provider.id}
                                            ref={(node) => {
                                                cardRefs.current[index] = node;
                                            }}
                                            provider={provider}
                                            query={query}
                                            tabIndex={index === current ? 0 : -1}
                                            onFocus={() => setActiveIndex(index)}
                                            onSelect={connect}
                                        />
                                    ))}
                                </div>
                            </TooltipProvider>
                        ))}

                    {step === "connecting" && selected && (
                        <OAuthConnectPanel
                            provider={selected}
                            state={flow.state}
                            toolCount={connectedServer?.discovered_tool_count ?? null}
                            onCancel={backToProviders}
                            onReopen={flow.reopen}
                            onContinueInTab={flow.continueInTab}
                            onRetry={() => connect(selected)}
                            onManual={goManual}
                            onOpenServer={flow.state.serverId ? () => openServer(flow.state.serverId as string) : undefined}
                        />
                    )}
                </div>

                {step === "providers" && (
                    <div className="border-t border-border px-6 py-3">
                        <Button variant="ghost" onClick={goManual} className="-mx-3 h-auto w-[calc(100%+1.5rem)] justify-between px-3 py-2">
                            <span className="text-sm text-muted-foreground">
                                Not listed? <span className="font-medium text-foreground">Configure manually</span> (stdio or HTTP)
                            </span>
                            <ArrowRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                        </Button>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}
