import React, { Suspense } from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { OverviewDashboard } from "@/features/overview/components/OverviewMetrics";
import { CardGridSkeleton } from "@/components/common/CardGridSkeleton";
import { RegisterServerButton } from "@/features/servers/components/RegisterServerButton";

export default function OverviewPage() {
    return (
        <div className="space-y-6">
            <PageHeader
                title="Hub Overview"
                description="Operational health, registered MCP servers and recent tool activity."
                actions={<RegisterServerButton size="sm" />}
            />

            <Suspense fallback={<CardGridSkeleton count={4} />}>
                <OverviewDashboard />
            </Suspense>
        </div>
    );
}
