"use client";

import React, { useEffect, useState } from "react";
import { Server as ServerIcon } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common/PageHeader";
import { ServerFilterParams } from "@/types";
import { useServers } from "@/features/servers/hooks/use-servers";
import { ServerListTable } from "@/features/servers/components/ServerListTable";
import { ServerFilterBar } from "@/features/servers/components/ServerFilterBar";
import { RegisterServerButton } from "@/features/servers/components/RegisterServerButton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { PaginationControl } from "@/components/common/PaginationControl";
import { TableSkeleton } from "@/components/common/TableSkeleton";
import { describeOAuthError } from "@/features/servers/hooks/use-oauth";

export default function ServersPage() {
    const [filters, setFilters] = useState<ServerFilterParams>({
        page: 1,
        page_size: 20,
        sort_by: "created_at",
        sort_order: "desc",
    });

    const { data, isLoading, isError, error, refetch } = useServers(filters);

    // A sign-in finished in this tab (popup blocked) and failed: /oauth/complete redirects here with the error.
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const oauthError = params.get("oauth_error");
        if (!oauthError) return;
        toast.error(`Sign-in failed: ${describeOAuthError(oauthError)}`);
        params.delete("oauth_error");
        const rest = params.toString();
        window.history.replaceState(null, "", window.location.pathname + (rest ? `?${rest}` : ""));
    }, []);

    const servers = data?.items || [];
    const total = data?.total || 0;
    const totalPages = data?.total_pages || 1;

    return (
        <div className="space-y-6">
            <PageHeader
                title="MCP Servers"
                description="Register and manage Model Context Protocol servers connected via stdio or streamable-http."
                actions={<RegisterServerButton />}
            />

            <ServerFilterBar filters={filters} onChange={setFilters} />

            {isError && (
                <ErrorAlert
                    title="Failed to fetch MCP servers"
                    message={(error as any)?.message || "An error occurred while loading server registrations"}
                    correlationId={(error as any)?.correlationId}
                    onRetry={() => refetch()}
                />
            )}

            {isLoading ? (
                <TableSkeleton
                    columns={["Server Name", "Transport", "Health Status", "Discovered Tools", "Last Connected", "Actions"]}
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
                    action={<RegisterServerButton label="Register New Server" />}
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
                        onPageSizeChange={(page_size) => setFilters((prev) => ({ ...prev, page_size, page: 1 }))}
                    />
                </>
            )}
        </div>
    );
}
