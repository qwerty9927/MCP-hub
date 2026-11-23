"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Activity, BarChart3, Trophy, Wrench } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { CardGridSkeleton } from "@/components/common/CardGridSkeleton";
import { TableSkeleton } from "@/components/common/TableSkeleton";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToolUsageReport, UsageRange } from "@/types";
import { useToolUsage } from "@/features/metrics/hooks/use-tool-usage";
import { ToolUsageChart } from "@/features/metrics/components/ToolUsageChart";
import { TOOL_USAGE_COLUMNS, ToolUsageTable } from "@/features/metrics/components/ToolUsageTable";
import { formatPercent } from "@/features/metrics/utils";

const TOP_TOOLS_LIMIT = 10;

const RANGE_OPTIONS: { value: UsageRange; label: string; description: string }[] = [
    { value: "24h", label: "24h", description: "in the last 24 hours" },
    { value: "7d", label: "7d", description: "in the last 7 days" },
    { value: "30d", label: "30d", description: "in the last 30 days" },
    { value: "all", label: "All", description: "across all time" },
];

export default function MetricsPage() {
    const [range, setRange] = useState<UsageRange>("7d");
    const { data, isLoading, isError, error, refetch } = useToolUsage(range, TOP_TOOLS_LIMIT);
    const rangeDescription = RANGE_OPTIONS.find((option) => option.value === range)?.description ?? "";

    return (
        <div className="space-y-6">
            <PageHeader
                title="Metrics"
                description="Which tools are called most, and how often those calls succeed."
                actions={
                    <Tabs value={range} onValueChange={(value) => setRange(value as UsageRange)}>
                        <TabsList aria-label="Time range">
                            {RANGE_OPTIONS.map((option) => (
                                <TabsTrigger key={option.value} value={option.value} onClick={() => setRange(option.value)}>
                                    {option.label}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                    </Tabs>
                }
            />

            {isError ? (
                <ErrorAlert
                    title="Failed to load tool usage"
                    message={(error as any)?.message || "Could not retrieve tool usage metrics"}
                    correlationId={(error as any)?.correlationId}
                    onRetry={() => refetch()}
                />
            ) : isLoading || !data ? (
                <>
                    <CardGridSkeleton count={3} className="lg:grid-cols-3" />
                    <TableSkeleton columns={TOOL_USAGE_COLUMNS} rowCount={5} showPagination={false} />
                </>
            ) : data.total_calls === 0 || data.items.length === 0 ? (
                <EmptyState
                    icon={BarChart3}
                    title="No tool calls yet"
                    description={`${
                        range === "all" ? "No tools have been called yet." : `No tools were called ${rangeDescription}.`
                    } Run a tool in the Playground to see usage here.`}
                    action={
                        <Button asChild>
                            <Link href="/playground">Run a Tool in Playground</Link>
                        </Button>
                    }
                />
            ) : (
                <UsageReport report={data} rangeDescription={rangeDescription} />
            )}
        </div>
    );
}

function UsageReport({ report, rangeDescription }: { report: ToolUsageReport; rangeDescription: string }) {
    const topTool = report.items[0];
    const listedCalls = report.items.reduce((sum, item) => sum + item.total_calls, 0);
    // The report lists at most TOP_TOOLS_LIMIT tools, so a full list means there may be more.
    const toolCount = report.items.length >= TOP_TOOLS_LIMIT ? `${report.items.length}+` : String(report.items.length);

    return (
        <>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <SummaryCard title="Calls in range" icon={Activity} value={report.total_calls.toLocaleString("en-US")}>
                    Tool calls {rangeDescription}
                </SummaryCard>
                <SummaryCard title="Distinct tools" icon={Wrench} value={toolCount}>
                    Tools called at least once
                </SummaryCard>
                <SummaryCard title="Most-used tool" icon={Trophy} value={topTool.tool_name} valueClassName="truncate text-xl">
                    {topTool.server_name} · {topTool.total_calls.toLocaleString("en-US")} calls (
                    {formatPercent(topTool.total_calls, report.total_calls)})
                </SummaryCard>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Top {TOP_TOOLS_LIMIT} tools</CardTitle>
                    <CardDescription>
                        Calls by status. These tools account for {formatPercent(listedCalls, report.total_calls)} of all calls{" "}
                        {rangeDescription}.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <ToolUsageChart items={report.items} />
                </CardContent>
            </Card>

            <ToolUsageTable items={report.items} totalCalls={report.total_calls} />
        </>
    );
}

interface SummaryCardProps {
    title: string;
    icon: React.ComponentType<{ className?: string }>;
    value: string;
    valueClassName?: string;
    children: React.ReactNode;
}

function SummaryCard({ title, icon: Icon, value, valueClassName, children }: SummaryCardProps) {
    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{title}</CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
                <div className={valueClassName ?? "text-2xl"} title={value}>
                    <span className="font-bold font-mono">{value}</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1 truncate">{children}</p>
            </CardContent>
        </Card>
    );
}
