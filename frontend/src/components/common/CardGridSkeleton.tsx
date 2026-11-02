"use client";

import React from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface CardGridSkeletonProps {
    count?: number;
    className?: string;
}

export function CardGridSkeleton({ count = 4, className }: CardGridSkeletonProps) {
    const items = Array.from({ length: count }, (_, i) => i);

    return (
        <div className={cn("grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4", className)}>
            {items.map((idx) => (
                <Card key={idx} className="p-4 space-y-3">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 p-0">
                        <Skeleton className="h-4 w-24" />
                        <Skeleton className="h-4 w-4 rounded-full" />
                    </CardHeader>
                    <CardContent className="p-0 space-y-2">
                        <Skeleton className="h-8 w-16" />
                        <Skeleton className="h-3 w-36" />
                    </CardContent>
                </Card>
            ))}
        </div>
    );
}
