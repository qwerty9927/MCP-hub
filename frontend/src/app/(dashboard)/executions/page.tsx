"use client";

import React, { useState } from "react";
import Link from "next/link";
import { History, Terminal } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { ExecutionFilterParams } from "@/types";
import { useExecutions } from "@/features/executions/hooks/use-executions";
import { ExecutionListTable } from "@/features/executions/components/ExecutionListTable";
import { ExecutionFilterBar } from "@/features/executions/components/ExecutionFilterBar";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { PaginationControl } from "@/components/common/PaginationControl";
import { TableSkeleton } from "@/components/common/TableSkeleton";

export default function ExecutionsPage() {
    const [filters, setFilters] = useState<ExecutionFilterParams>({
        page: 1,
        page_size: 20,
    });

    const { data, isLoading, isError, error, refetch } = useExecutions(filters);

    const executions = data?.items || [];
    const total = data?.total || 0;
    const totalPages = data?.total_pages || 1;

    return (
        <div className="space-y-6">
            <PageHeader
                title="Execution History"
                description="Audit log of all MCP tool invocations, duration benchmarks, and error diagnostics."
                actions={
                    <Button asChild className="gap-2">
                        <Link href="/playground">
                            <Terminal className="h-4 w-4" />
                            Open Playground
                        </Link>
                    </Button>
                }
            />

            <ExecutionFilterBar filters={filters} onChange={setFilters} />

            {isError && (
                <ErrorAlert
                    title="Failed to fetch execution records"
                    message={(error as any)?.message || "Could not retrieve execution history"}
                    correlationId={(error as any)?.correlationId}
                    onRetry={() => refetch()}
                />
            )}

            {isLoading ? (
                <TableSkeleton
                    columns={[
                        "Tool Name",
                        "Server",
                        "Status",
                        "Duration",
                        "Executed At",
                        "Actions",
                    ]}
                    rowCount={(filters.page_size ?? 0 > 5) ? 5 : filters.page_size}
                />
            ) : executions.length === 0 ? (
                <EmptyState
                    icon={History}
                    title="No execution records found"
                    description={
                        filters.tool_name || filters.server_id || filters.is_error !== undefined
                            ? "No execution entries match your filter criteria."
                            : "No tools have been executed yet. Run a tool in the Playground to see results logged here."
                    }
                    action={
                        <Button asChild>
                            <Link href="/playground">Run a Tool in Playground</Link>
                        </Button>
                    }
                />
            ) : (
                <>
                    <ExecutionListTable executions={executions} />
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
