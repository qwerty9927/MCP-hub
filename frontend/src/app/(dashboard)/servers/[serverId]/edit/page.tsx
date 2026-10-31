"use client";

import React, { use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { ServerForm } from "@/features/servers/components/ServerForm";
import { useServer, useUpdateServer } from "@/features/servers/hooks/use-servers";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorAlert } from "@/components/common/ErrorAlert";

interface ServerEditPageProps {
    params: Promise<{ serverId: string }>;
}

export default function ServerEditPage({ params }: ServerEditPageProps) {
    const { serverId } = use(params);
    const router = useRouter();

    const { data: server, isLoading, isError, error, refetch } = useServer(serverId);
    const updateMutation = useUpdateServer();

    const handleSubmit = async (payload: any) => {
        await updateMutation.mutateAsync({ id: serverId, payload });
        router.push(`/servers/${serverId}`);
    };

    if (isLoading) {
        return (
            <div className="max-w-4xl mx-auto space-y-6">
                <Skeleton className="h-8 w-48" />
                <Skeleton className="h-64 w-full" />
            </div>
        );
    }

    if (isError || !server) {
        return (
            <div className="max-w-4xl mx-auto space-y-6">
                <Button asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
                    <Link href="/servers">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Servers
                    </Link>
                </Button>
                <ErrorAlert
                    title="Server Not Found"
                    message={(error as any)?.message || "Could not find server to edit."}
                    onRetry={() => refetch()}
                />
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="flex items-center gap-2">
                <Button asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
                    <Link href={`/servers/${serverId}`}>
                        <ArrowLeft className="h-4 w-4" />
                        Back to Server Details
                    </Link>
                </Button>
            </div>

            <PageHeader
                title={`Edit Server: ${server.name}`}
                description="Modify transport configuration, descriptions, or toggle execution status."
            />

            <ServerForm
                initialData={server}
                onSubmit={handleSubmit}
                isLoading={updateMutation.isPending}
                onCancel={() => router.push(`/servers/${serverId}`)}
            />
        </div>
    );
}
