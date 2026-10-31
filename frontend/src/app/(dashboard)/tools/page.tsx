"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Wrench, Terminal } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { ToolFilterParams } from "@/types";
import { useTools } from "@/features/tools/hooks/use-tools";
import { ToolListTable } from "@/features/tools/components/ToolListTable";
import { ToolFilterBar } from "@/features/tools/components/ToolFilterBar";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { PaginationControl } from "@/components/common/PaginationControl";
import { Skeleton } from "@/components/ui/skeleton";

export default function ToolsCatalogPage() {
    const [filters, setFilters] = useState<ToolFilterParams>({
        page: 1,
        page_size: 20,
    });

    const { data, isLoading, isError, error, refetch } = useTools(filters);

    const tools = data?.items || [];
    const total = data?.total || 0;
    const totalPages = data?.total_pages || 1;

    return (
        <div className="space-y-6">
            <PageHeader
                title="Unified Tool Catalog"
                description="Search, inspect schemas, and test discovered MCP tools across all registered servers."
                actions={
                    <Button asChild className="gap-2">
                        <Link href="/playground">
                            <Terminal className="h-4 w-4" />
                            Open Playground
                        </Link>
                    </Button>
                }
            />

            <ToolFilterBar filters={filters} onChange={setFilters} />

            {isError && (
                <ErrorAlert
                    title="Failed to fetch tool catalog"
                    message={
                        (error as any)?.message ||
                        "Could not retrieve discovered tools from backend"
                    }
                    correlationId={(error as any)?.correlationId}
                    onRetry={() => refetch()}
                />
            )}

            {isLoading ? (
                <div className="space-y-3">
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-16 w-full" />
                    <Skeleton className="h-16 w-full" />
                    <Skeleton className="h-16 w-full" />
                </div>
            ) : tools.length === 0 ? (
                <EmptyState
                    icon={Wrench}
                    title="No tools discovered"
                    description={
                        filters.search || filters.server_id || filters.status
                            ? "No tools match your current filter parameters."
                            : "No tools have been discovered yet. Connect to a registered MCP server to discover its tools."
                    }
                    action={
                        <Button asChild>
                            <Link href="/servers">Go to Servers</Link>
                        </Button>
                    }
                />
            ) : (
                <>
                    <ToolListTable tools={tools} />
                    <PaginationControl
                        page={filters.page || 1}
                        pageSize={filters.page_size || 20}
                        total={total}
                        totalPages={totalPages}
                        onPageChange={(page) => setFilters((prev) => ({ ...prev, page }))}
                        onPageSizeChange={(page_size) =>
                            setFilters((prev) => ({ ...prev, page_size, page: 1 }))
                        }
                    />
                </>
            )}
        </div>
    );
}
