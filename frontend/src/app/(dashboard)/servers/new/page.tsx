"use client";

import React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { ServerForm } from "@/features/servers/components/ServerForm";
import { useCreateServer } from "@/features/servers/hooks/use-servers";

export default function NewServerPage() {
    const router = useRouter();
    const createMutation = useCreateServer();

    const handleSubmit = async (payload: any) => {
        const created = await createMutation.mutateAsync(payload);
        router.push(`/servers/${created.id}`);
    };

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="flex items-center gap-2 mb-2">
                <Button asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
                    <Link href="/servers">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Servers
                    </Link>
                </Button>
            </div>

            <PageHeader
                title="Register MCP Server"
                description="Configure a new Model Context Protocol server. The backend will validate transport parameters."
            />

            <ServerForm
                onSubmit={handleSubmit}
                isLoading={createMutation.isPending}
                onCancel={() => router.push("/servers")}
            />
        </div>
    );
}
