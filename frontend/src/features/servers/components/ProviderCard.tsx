"use client";

import React, { useId, useState } from "react";
import { badgeVariants } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { OAuthProvider } from "@/types";

/** The host of a provider's MCP URL (`mcp.linear.app`), or the URL itself if it doesn't parse. */
export function providerHost(url: string): string {
    try {
        return new URL(url).host;
    } catch {
        return url;
    }
}

/** Wraps every case-insensitive match of `query` in `text` with a highlight mark. */
export function Highlight({ text, query }: { text: string; query?: string }) {
    const needle = query?.trim().toLowerCase();
    if (!needle) return <>{text}</>;

    const parts: React.ReactNode[] = [];
    const haystack = text.toLowerCase();
    let from = 0;
    for (let at = haystack.indexOf(needle); at !== -1; at = haystack.indexOf(needle, from)) {
        if (at > from) parts.push(text.slice(from, at));
        parts.push(
            <mark key={at} className="rounded-sm bg-primary/15 px-0.5 text-foreground">
                {text.slice(at, at + needle.length)}
            </mark>
        );
        from = at + needle.length;
    }
    if (from < text.length) parts.push(text.slice(from));
    return <>{parts}</>;
}

/** The provider's logo, or a monogram tile with its first letter. */
export function ProviderTile({ provider, size = "md" }: { provider: Pick<OAuthProvider, "name" | "logo">; size?: "md" | "lg" }) {
    const [logoFailed, setLogoFailed] = useState(false);
    const box = size === "lg" ? "h-14 w-14 rounded-xl text-xl" : "h-10 w-10 rounded-lg text-base";

    if (provider.logo && !logoFailed) {
        return (
            // eslint-disable-next-line @next/next/no-img-element -- logos are small external images from the catalog
            <img
                src={provider.logo}
                alt=""
                aria-hidden="true"
                onError={() => setLogoFailed(true)}
                className={cn("shrink-0 border border-border bg-card object-contain p-1.5", box)}
            />
        );
    }
    return (
        <span
            aria-hidden="true"
            className={cn(
                "flex shrink-0 items-center justify-center border border-primary/20 bg-primary/10 font-semibold text-primary",
                box
            )}
        >
            {provider.name.charAt(0).toUpperCase()}
        </span>
    );
}

interface ProviderCardProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onSelect" | "disabled"> {
    provider: OAuthProvider;
    /** The search text, highlighted in the name, description and host. */
    query?: string;
    onSelect: (provider: OAuthProvider) => void;
}

/**
 * One provider in the Register Server picker; the whole card is the button. A provider that needs an OAuth client
 * the admin hasn't configured is shown dimmed with a "Needs setup" badge and can't be selected (it stays focusable
 * so its tooltip, which names the setting, can be reached from the keyboard).
 */
export const ProviderCard = React.forwardRef<HTMLButtonElement, ProviderCardProps>(
    ({ provider, query, onSelect, className, onClick, ...props }, ref) => {
        const descriptionId = useId();
        const unavailable = !provider.available;
        const host = providerHost(provider.mcp_url);

        const card = (
            <button
                {...props}
                ref={ref}
                type="button"
                aria-disabled={unavailable || undefined}
                aria-describedby={descriptionId}
                data-provider-id={provider.id}
                onClick={(event) => {
                    onClick?.(event);
                    if (!unavailable && !event.defaultPrevented) onSelect(provider);
                }}
                className={cn(
                    "flex w-full items-start gap-3 rounded-lg border border-border bg-card p-3 text-left transition-colors",
                    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                    unavailable ? "cursor-not-allowed opacity-60" : "hover:border-primary/40 hover:bg-accent/50",
                    className
                )}
            >
                <ProviderTile provider={provider} />
                <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                        <span className="truncate text-sm font-semibold text-foreground">
                            <Highlight text={provider.name} query={query} />
                        </span>
                        <span className="ml-auto shrink-0">
                            {unavailable ? (
                                <span className={badgeVariants({ variant: "muted" })}>Needs setup</span>
                            ) : provider.connected_count > 0 ? (
                                <span className={badgeVariants({ variant: "success" })}>Connected</span>
                            ) : (
                                <span className={cn(badgeVariants({ variant: "outline" }), "font-medium text-muted-foreground")}>
                                    OAuth
                                </span>
                            )}
                        </span>
                    </span>
                    <span id={descriptionId} className="mt-0.5 block truncate text-xs text-muted-foreground">
                        <Highlight text={provider.description} query={query} />
                        {unavailable && <span className="sr-only">. Needs setup by an admin before it can be connected.</span>}
                    </span>
                    <span className="mt-1 block truncate font-mono text-[11px] text-muted-foreground">
                        <Highlight text={host} query={query} />
                    </span>
                </span>
            </button>
        );

        if (!unavailable) return card;
        return (
            <Tooltip>
                <TooltipTrigger asChild>{card}</TooltipTrigger>
                <TooltipContent>
                    {provider.client_env ? (
                        <>
                            Set <span className="font-mono">{provider.client_env}</span> on the backend to connect {provider.name}.
                        </>
                    ) : (
                        <>An admin must configure an OAuth client for {provider.name}.</>
                    )}
                </TooltipContent>
            </Tooltip>
        );
    }
);
ProviderCard.displayName = "ProviderCard";
