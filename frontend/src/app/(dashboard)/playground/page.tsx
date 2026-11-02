import React, { Suspense } from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { ToolPlayground } from "@/features/playground/components/ToolPlayground";
import { Skeleton } from "@/components/ui/skeleton";

export default function PlaygroundPage() {
    return (
        <div className="space-y-6">
            <PageHeader
                title="Tool Playground"
                description="Safely test and inspect MCP tool execution against active server sessions."
            />

            <Suspense
                fallback={
                    <div className="space-y-6">
                        {/* Target selector card skeleton */}
                        <div className="rounded-xl border border-border bg-card p-6 space-y-4">
                            <Skeleton className="h-5 w-48" />
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Skeleton className="h-4 w-20" />
                                    <Skeleton className="h-9 w-full rounded-md" />
                                </div>
                                <div className="space-y-2">
                                    <Skeleton className="h-4 w-20" />
                                    <Skeleton className="h-9 w-full rounded-md" />
                                </div>
                            </div>
                        </div>

                        {/* Two columns grid skeleton */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div className="rounded-xl border border-border bg-card p-6 space-y-4">
                                <Skeleton className="h-6 w-36" />
                                <Skeleton className="h-12 w-full rounded-md" />
                                <Skeleton className="h-12 w-full rounded-md" />
                                <Skeleton className="h-12 w-full rounded-md" />
                                <div className="pt-4 border-t border-border flex justify-between">
                                    <Skeleton className="h-4 w-24" />
                                    <Skeleton className="h-9 w-28 rounded-md" />
                                </div>
                            </div>
                            <div className="rounded-xl border border-border bg-card p-6 space-y-4">
                                <Skeleton className="h-6 w-36" />
                                <Skeleton className="h-48 w-full rounded-md" />
                            </div>
                        </div>
                    </div>
                }
            >
                <ToolPlayground />
            </Suspense>
        </div>
    );
}
