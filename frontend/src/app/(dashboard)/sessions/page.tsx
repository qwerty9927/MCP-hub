"use client";

import React, { useState } from "react";
import { Bot } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { SessionFilterParams } from "@/types";
import { useSessions } from "@/features/sessions/hooks/use-sessions";
import { SessionListTable } from "@/features/sessions/components/SessionListTable";
import { SessionFilterBar } from "@/features/sessions/components/SessionFilterBar";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { PaginationControl } from "@/components/common/PaginationControl";
import { TableSkeleton } from "@/components/common/TableSkeleton";

export default function SessionsPage() {
    const [filters, setFilters] = useState<SessionFilterParams>({
        page: 1,
        page_size: 20,
    });
    const [autoRefresh, setAutoRefresh] = useState(false);

    const { data, isLoading, isFetching, isError, error, refetch } = useSessions(filters, {
        refetchInterval: autoRefresh ? 10000 : false,
    });

    const sessions = data?.items || [];
    const total = data?.total || 0;
    const totalPages = data?.total_pages || 1;

    return (
        <div className="space-y-6">
            <PageHeader
                title="MCP Sessions"
                description="Browse active and historical agent client sessions and inspect their MCP tool executions."
            />

            <SessionFilterBar
                filters={filters}
                onChange={setFilters}
                onRefresh={() => refetch()}
                isRefreshing={isFetching}
                autoRefresh={autoRefresh}
                onToggleAutoRefresh={setAutoRefresh}
            />

            {isError && (
                <ErrorAlert
                    title="Failed to fetch sessions"
                    message={(error as any)?.message || "Could not retrieve MCP sessions list"}
                    correlationId={(error as any)?.correlationId}
                    onRetry={() => refetch()}
                />
            )}

            {isLoading ? (
                <TableSkeleton
                    columns={["Session ID", "Title / Identifier", "Status", "Total Tool Calls", "Created", "Last Activity", "Actions"]}
                    rowCount={(filters.page_size ?? 0) > 5 ? 5 : filters.page_size}
                />
            ) : sessions.length === 0 ? (
                <EmptyState
                    icon={Bot}
                    title="No sessions found"
                    description={
                        filters.search || filters.status
                            ? "No sessions match your filter criteria."
                            : "No agent sessions have been recorded yet. Connect an agent client or run tools with a session ID to populate sessions."
                    }
                />
            ) : (
                <>
                    <SessionListTable sessions={sessions} />
                    <PaginationControl
                        page={filters.page || 1}
                        pageSize={filters.page_size || 20}
                        total={total}
                        totalPages={totalPages}
                        onPageChange={(page) => setFilters((prev) => ({ ...prev, page }))}
                        onPageSizeChange={(page_size) => setFilters((prev) => ({ ...prev, page_size, page: 1 }))}
                    />
                </>
            )}
        </div>
    );
}
