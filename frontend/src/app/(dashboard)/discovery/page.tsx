"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { Compass, Settings2 } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { InfoCallout } from "@/components/common/InfoCallout";
import { PendingBadge } from "@/components/common/PendingBackend";
import { SearchInput } from "@/components/common/SearchInput";
import { SegmentedControl } from "@/components/common/SegmentedControl";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ProviderCard } from "@/features/servers/components/ProviderCard";
import { RegisterServerDialog, filterProviders, MANUAL_REGISTER_PATH } from "@/features/servers/components/RegisterServerDialog";
import { useOAuthProviders } from "@/features/servers/hooks/use-oauth";
import { OAuthProvider } from "@/types";

const ALL = "__all__";

/** Discovery: hosted MCP servers the hub can connect through OAuth, filterable by category. */
export default function DiscoveryPage() {
    const { data, isLoading, isError, error, refetch } = useOAuthProviders(true);
    const [query, setQuery] = useState("");
    const [category, setCategory] = useState<string>(ALL);
    const [picked, setPicked] = useState<OAuthProvider | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);

    const providers = useMemo(() => data ?? [], [data]);
    const categories = useMemo(() => Array.from(new Set(providers.map((provider) => provider.category))).sort(), [providers]);
    const filtered = useMemo(() => filterProviders(providers, query, category === ALL ? null : category), [providers, query, category]);
    const connected = providers.filter((provider) => provider.connected_count > 0).length;

    const pick = (provider: OAuthProvider) => {
        setPicked(provider);
        setDialogOpen(true);
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Discovery"
                description="Hosted MCP servers you can connect with your account. Pick one to sign in and register it."
                actions={
                    <Button asChild variant="outline" size="sm" className="gap-1.5">
                        <Link href={MANUAL_REGISTER_PATH}>
                            <Settings2 className="h-4 w-4" aria-hidden="true" />
                            Configure Manually
                        </Link>
                    </Button>
                }
            />

            <InfoCallout title="More catalogs are coming" action={<PendingBadge id="remote-catalog" />}>
                Remote MCP catalogs, such as Cloudflare&rsquo;s, will be listed here once the hub can serve them.
            </InfoCallout>

            <div className="flex flex-wrap items-center gap-3">
                <SearchInput
                    label="Search providers"
                    placeholder="Search name, host or purpose"
                    clearLabel="Clear provider search"
                    value={query}
                    onValueChange={setQuery}
                    className="w-full sm:w-[320px]"
                />
                {categories.length > 1 && (
                    <SegmentedControl
                        label="Filter by category"
                        value={category}
                        onValueChange={setCategory}
                        options={[{ value: ALL, label: "All" }, ...categories.map((value) => ({ value, label: value }))]}
                        className="flex-wrap"
                    />
                )}
                {!isLoading && providers.length > 0 && (
                    <span className="text-xs text-muted-foreground sm:ml-auto" aria-live="polite">
                        Showing <span className="font-mono">{filtered.length}</span> of {providers.length} · {connected} connected
                    </span>
                )}
            </div>

            {isLoading ? (
                <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
                    {Array.from({ length: 6 }).map((_, index) => (
                        <Skeleton key={index} className="h-[84px] rounded-lg" />
                    ))}
                </div>
            ) : isError ? (
                <ErrorAlert
                    title="Couldn't load providers"
                    message={(error as { message?: string } | null)?.message || "The provider list is unavailable."}
                    correlationId={(error as { correlationId?: string } | null)?.correlationId}
                    onRetry={() => refetch()}
                />
            ) : providers.length === 0 ? (
                <EmptyState
                    icon={Compass}
                    title="No providers available"
                    description="This hub has no hosted providers configured. You can still register a server manually."
                    action={
                        <Button asChild size="sm">
                            <Link href={MANUAL_REGISTER_PATH}>Configure Manually</Link>
                        </Button>
                    }
                />
            ) : filtered.length === 0 ? (
                <EmptyState
                    icon={Compass}
                    title="No providers match these filters"
                    description="Try another search or category."
                    action={
                        <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                                setQuery("");
                                setCategory(ALL);
                            }}
                        >
                            Clear Filters
                        </Button>
                    }
                />
            ) : (
                <TooltipProvider delayDuration={150}>
                    <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
                        {filtered.map((provider) => (
                            <ProviderCard key={provider.id} provider={provider} query={query} onSelect={pick} className="p-4" />
                        ))}
                    </div>
                </TooltipProvider>
            )}

            {picked && <RegisterServerDialog open={dialogOpen} onOpenChange={setDialogOpen} initialProvider={picked} />}
        </div>
    );
}
