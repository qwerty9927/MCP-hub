"use client";

import React from "react";
import { Skeleton } from "@/components/ui/skeleton";

interface ListSkeletonProps {
    count?: number;
}

export function ListSkeleton({ count = 4 }: ListSkeletonProps) {
    const items = Array.from({ length: count }, (_, i) => i);

    return (
        <div className="space-y-3">
            {items.map((idx) => (
                <div key={idx} className="flex items-center justify-between rounded-lg border border-border p-3">
                    <div className="space-y-2 flex-1 pr-3">
                        <Skeleton className="h-4 w-36" />
                        <Skeleton className="h-3 w-48" />
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                        <Skeleton className="h-6 w-20 rounded-full" />
                    </div>
                </div>
            ))}
        </div>
    );
}
