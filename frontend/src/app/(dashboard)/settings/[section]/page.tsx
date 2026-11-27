import React from "react";
import { notFound } from "next/navigation";
import { Clock } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { PendingBadge } from "@/components/common/PendingBackend";
import { PENDING_SECTIONS } from "@/features/settings/sections";

interface PendingSectionPageProps {
    params: Promise<{ section: string }>;
}

/** Settings sections that are designed but wait for the backend; any other slug is a 404. */
export default async function PendingSectionPage({ params }: PendingSectionPageProps) {
    const { section } = await params;
    const entry = PENDING_SECTIONS[section];
    if (!entry) notFound();

    return (
        <div className="flex flex-col gap-7">
            <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-bold tracking-tight">{entry.label}</h2>
                <PendingBadge id={entry.pending} />
            </div>
            <EmptyState
                icon={Clock}
                title={`${entry.label} is on the way`}
                description={`${entry.description ?? ""} This page goes live once the hub's backend supports it.`}
            />
        </div>
    );
}
