"use client";

import React, { use, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Clock, History, LayoutList, Layers, ArrowDownUp, Filter } from "lucide-react";
import { useSession, useSessionToolCalls } from "@/features/sessions/hooks/use-sessions";
import { SessionOverview } from "@/features/sessions/components/SessionOverview";
import { ToolExecutionTimeline } from "@/features/sessions/components/ToolExecutionTimeline";
import { ServerToolGroup } from "@/features/sessions/components/ServerToolGroup";
import { ToolCallDetailDrawer } from "@/features/sessions/components/ToolCallDetailDrawer";
import { SessionToolCallFilterParams, ToolCallRead } from "@/types";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CardGridSkeleton } from "@/components/common/CardGridSkeleton";
import { ListSkeleton } from "@/components/common/ListSkeleton";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { PaginationControl } from "@/components/common/PaginationControl";
import { Skeleton } from "@/components/ui/skeleton";

interface SessionDetailPageProps {
    params: Promise<{ sessionId: string }>;
}

export default function SessionDetailPage({ params }: SessionDetailPageProps) {
    const { sessionId } = use(params);

    // Display mode: "timeline" (Mode A, default) or "grouped" (Mode B)
    const [displayMode, setDisplayMode] = useState<"timeline" | "grouped">("timeline");

    // Tool call pagination and filter criteria
    const [toolFilters, setToolFilters] = useState<SessionToolCallFilterParams>({
        page: 1,
        page_size: 50,
        sort_by: "created_at",
        order: "asc", // Default to chronological oldest first
    });

    // Selected tool call for drawer
    const [selectedCallId, setSelectedCallId] = useState<string | null>(null);

    // Fetch session overview metrics
    const {
        data: session,
        isLoading: isSessionLoading,
        isError: isSessionError,
        error: sessionError,
        refetch: refetchSession,
    } = useSession(sessionId);

    // Fetch session tool calls list (shared dataset for both Timeline and Grouped modes)
    const {
        data: toolCallsData,
        isLoading: isToolsLoading,
        isFetching: isToolsFetching,
        isError: isToolsError,
        error: toolsError,
        refetch: refetchToolCalls,
    } = useSessionToolCalls(sessionId, toolFilters);

    const toolCalls = toolCallsData?.items || [];
    const totalCalls = toolCallsData?.total || 0;
    const totalPages = toolCallsData?.total_pages || 1;

    // Preserve selected tool call object from loaded dataset
    const selectedCall = toolCalls.find((call) => call.id === selectedCallId) || null;

    const handleSelectCall = (call: ToolCallRead) => {
        setSelectedCallId(call.id);
    };

    const handleSortOrderChange = (newOrder: "asc" | "desc") => {
        setToolFilters((prev) => ({
            ...prev,
            order: newOrder,
            page: 1,
        }));
    };

    const handleStatusFilterChange = (statusVal: string) => {
        setToolFilters((prev) => ({
            ...prev,
            status: statusVal === "all" ? undefined : statusVal,
            page: 1,
        }));
    };

    if (isSessionLoading) {
        return (
            <div className="space-y-6">
                <div className="flex items-center gap-2">
                    <Skeleton className="h-8 w-36 rounded-md" />
                </div>
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between pb-6 border-b border-border">
                    <div className="space-y-2">
                        <Skeleton className="h-8 w-64" />
                        <Skeleton className="h-4 w-96 max-w-full" />
                    </div>
                </div>
                <CardGridSkeleton count={6} />
                <ListSkeleton count={5} />
            </div>
        );
    }

    if (isSessionError || !session) {
        return (
            <div className="space-y-6">
                <Button asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
                    <Link href="/sessions">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Sessions
                    </Link>
                </Button>
                <ErrorAlert
                    title="Session Not Found"
                    message={(sessionError as any)?.message || "Could not locate session with the given ID."}
                    correlationId={(sessionError as any)?.correlationId}
                    onRetry={() => refetchSession()}
                />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Session Overview Top Section */}
            <SessionOverview
                session={session}
                onRefresh={() => {
                    refetchSession();
                    refetchToolCalls();
                }}
                isRefreshing={isToolsFetching}
            />

            {/* Tool Execution History Section */}
            <div className="space-y-4 pt-4 border-t border-border">
                {/* Control bar: View Mode Switcher, Sort Order, Status Filter */}
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    {/* Mode Selector Tabs (Timeline vs Group by MCP Server) */}
                    <div className="flex items-center gap-3">
                        <Tabs value={displayMode} onValueChange={(val: any) => setDisplayMode(val)} className="w-auto">
                            <TabsList className="grid grid-cols-2 h-9 p-1">
                                <TabsTrigger value="timeline" className="gap-1.5 text-xs">
                                    <History className="h-3.5 w-3.5" />
                                    Timeline
                                </TabsTrigger>
                                <TabsTrigger value="grouped" className="gap-1.5 text-xs">
                                    <Layers className="h-3.5 w-3.5" />
                                    Group by Server
                                </TabsTrigger>
                            </TabsList>
                        </Tabs>
                    </div>

                    {/* Filter and Sorting Controls */}
                    <div className="flex flex-wrap items-center gap-2">
                        {/* Status Filter */}
                        <Select value={toolFilters.status || "all"} onValueChange={handleStatusFilterChange}>
                            <SelectTrigger className="h-9 w-[130px] text-xs">
                                <Filter className="h-3 w-3 mr-1 text-muted-foreground" />
                                <SelectValue placeholder="All Status" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Status</SelectItem>
                                <SelectItem value="completed">Completed</SelectItem>
                                <SelectItem value="failed">Failed</SelectItem>
                                <SelectItem value="running">Running</SelectItem>
                            </SelectContent>
                        </Select>

                        {/* Chronological Sorting Switcher (Oldest First vs Newest First) */}
                        <Select value={toolFilters.order || "asc"} onValueChange={(val: any) => handleSortOrderChange(val)}>
                            <SelectTrigger className="h-9 w-[145px] text-xs font-medium">
                                <ArrowDownUp className="h-3 w-3 mr-1 text-primary" />
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="asc">Oldest First</SelectItem>
                                <SelectItem value="desc">Newest First</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                {isToolsError && (
                    <ErrorAlert
                        title="Failed to load session tool calls"
                        message={(toolsError as any)?.message || "Could not retrieve tool executions for this session."}
                        correlationId={(toolsError as any)?.correlationId}
                        onRetry={() => refetchToolCalls()}
                    />
                )}

                {isToolsLoading ? (
                    <ListSkeleton count={4} />
                ) : (
                    <>
                        {/* Render Active View Mode with Shared Dataset */}
                        {displayMode === "timeline" ? (
                            <ToolExecutionTimeline toolCalls={toolCalls} selectedCallId={selectedCallId} onSelectCall={handleSelectCall} />
                        ) : (
                            <ServerToolGroup toolCalls={toolCalls} selectedCallId={selectedCallId} onSelectCall={handleSelectCall} />
                        )}

                        {/* Pagination for tool executions */}
                        {toolCalls.length > 0 && (
                            <PaginationControl
                                page={toolFilters.page || 1}
                                pageSize={toolFilters.page_size || 50}
                                total={totalCalls}
                                totalPages={totalPages}
                                onPageChange={(page) => setToolFilters((prev) => ({ ...prev, page }))}
                                onPageSizeChange={(page_size) => setToolFilters((prev) => ({ ...prev, page_size, page: 1 }))}
                            />
                        )}
                    </>
                )}
            </div>

            {/* Slide-over Detail Drawer */}
            <ToolCallDetailDrawer
                toolCall={selectedCall}
                open={Boolean(selectedCall)}
                onOpenChange={(open) => {
                    if (!open) {
                        setSelectedCallId(null);
                    }
                }}
            />
        </div>
    );
}
