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
                    <div className="space-y-4">
                        <Skeleton className="h-24 w-full" />
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <Skeleton className="h-80 w-full" />
                            <Skeleton className="h-80 w-full" />
                        </div>
                    </div>
                }
            >
                <ToolPlayground />
            </Suspense>
        </div>
    );
}
