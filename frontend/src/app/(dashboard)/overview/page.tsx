import React, { Suspense } from "react";
import Link from "next/link";
import { Plus, Terminal } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { OverviewDashboard } from "@/features/overview/components/OverviewMetrics";
import { CardGridSkeleton } from "@/components/common/CardGridSkeleton";

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
                        <Button asChild size="sm" className="gap-1.5">
                            <Link href="/servers/new">
                                <Plus className="h-4 w-4" />
                                Register Server
                            </Link>
                        </Button>
                    </div>
                }
            />

            <Suspense fallback={<CardGridSkeleton count={4} />}>
                <OverviewDashboard />
            </Suspense>
        </div>
    );
}
