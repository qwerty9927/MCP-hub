"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Plus, Server as ServerIcon } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { ServerFilterParams } from "@/types";
import { useServers } from "@/features/servers/hooks/use-servers";
import { ServerListTable } from "@/features/servers/components/ServerListTable";
import { ServerFilterBar } from "@/features/servers/components/ServerFilterBar";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { PaginationControl } from "@/components/common/PaginationControl";
import { TableSkeleton } from "@/components/common/TableSkeleton";

export default function ServersPage() {
    const [filters, setFilters] = useState<ServerFilterParams>({
        page: 1,
        page_size: 20,
        sort_by: "created_at",
        sort_order: "desc",
    });

    const { data, isLoading, isError, error, refetch } = useServers(filters);

    const servers = data?.items || [];
    const total = data?.total || 0;
    const totalPages = data?.total_pages || 1;

    return (
        <div className="space-y-6">
            <PageHeader
                title="MCP Servers"
                description="Register and manage Model Context Protocol servers connected via stdio or streamable-http."
                actions={
                    <Button asChild className="gap-2">
                        <Link href="/servers/new">
                            <Plus className="h-4 w-4" />
                            Register Server
                        </Link>
                    </Button>
                }
            />

            <ServerFilterBar filters={filters} onChange={setFilters} />

            {isError && (
                <ErrorAlert
                    title="Failed to fetch MCP servers"
                    message={
                        (error as any)?.message ||
                        "An error occurred while loading server registrations"
                    }
                    correlationId={(error as any)?.correlationId}
                    onRetry={() => refetch()}
                />
            )}

            {isLoading ? (
                <TableSkeleton
                    columns={[
                        "Server Name",
                        "Transport",
                        "Health Status",
                        "Discovered Tools",
                        "Last Connected",
                        "Actions",
                    ]}
                    rowCount={(filters.page_size ?? 0 > 5) ? 5 : filters.page_size}
                />
            ) : servers.length === 0 ? (
                <EmptyState
                    icon={ServerIcon}
                    title="No MCP servers found"
                    description={
                        filters.search || filters.transport || filters.health_status
                            ? "No servers match the selected filter criteria. Try adjusting your search."
                            : "No MCP servers have been registered yet. Add your first server to discover tools."
                    }
                    action={
                        <Button asChild>
                            <Link href="/servers/new">
                                <Plus className="mr-2 h-4 w-4" />
                                Register New Server
                            </Link>
                        </Button>
                    }
                />
            ) : (
                <>
                    <ServerListTable servers={servers} />
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
