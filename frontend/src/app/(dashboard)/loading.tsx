import React from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { TableSkeleton } from "@/components/common/TableSkeleton";

export default function DashboardLoading() {
    return (
        <div className="space-y-6">
            {/* Top subtle progress shimmer */}
            <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-primary/60 to-transparent animate-pulse rounded-full" />

            {/* Page Header Skeleton */}
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between pb-6 border-b border-border mb-6">
                <div className="space-y-2">
                    <Skeleton className="h-8 w-56" />
                    <Skeleton className="h-4 w-96 max-w-full" />
                </div>
                <div className="flex items-center gap-2">
                    <Skeleton className="h-9 w-28 rounded-md" />
                </div>
            </div>

            {/* Filter / Search Controls Skeleton */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between py-2">
                <div className="flex flex-1 flex-wrap items-center gap-2">
                    <Skeleton className="h-9 w-64 max-w-sm rounded-md" />
                    <Skeleton className="h-9 w-36 rounded-md" />
                    <Skeleton className="h-9 w-32 rounded-md" />
                </div>
            </div>

            {/* Main Content Table Skeleton */}
            <TableSkeleton rowCount={5} columns={5} />
        </div>
    );
}
