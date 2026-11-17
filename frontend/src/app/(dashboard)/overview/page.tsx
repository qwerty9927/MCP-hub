import React, { Suspense } from "react";
import Link from "next/link";
import { Terminal } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { OverviewDashboard } from "@/features/overview/components/OverviewMetrics";
import { CardGridSkeleton } from "@/components/common/CardGridSkeleton";
import { RegisterServerButton } from "@/features/servers/components/RegisterServerButton";

export default function OverviewPage() {
    return (
        <div className="space-y-6">
            <PageHeader
                title="Hub Overview"
                description="Operational health, registered MCP servers, discovered tool count, and live invocation metrics."
                actions={
                    <div className="flex items-center gap-2">
                        <Button asChild variant="outline" size="sm" className="gap-1.5">
                            <Link href="/playground">
                                <Terminal className="h-4 w-4" />
                                Playground
                            </Link>
                        </Button>
                        <RegisterServerButton size="sm" />
                    </div>
                }
            />

            <Suspense fallback={<CardGridSkeleton count={4} />}>
                <OverviewDashboard />
            </Suspense>
        </div>
    );
}
