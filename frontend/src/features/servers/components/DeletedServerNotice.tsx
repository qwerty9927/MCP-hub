import React from "react";
import Link from "next/link";
import { ArrowLeft, History, Server, ServerOff } from "lucide-react";
import { Button } from "@/components/ui/button";

interface DeletedServerNoticeProps {
    /** The name stored on the execution that linked here, if known. */
    serverName: string | null;
}

/** Shown when a server opened from execution history no longer exists. */
export function DeletedServerNotice({ serverName }: DeletedServerNoticeProps) {
    return (
        <div className="space-y-6">
            <Button asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
                <Link href="/executions">
                    <ArrowLeft className="h-4 w-4" />
                    Back to Execution History
                </Link>
            </Button>
            <div
                role="status"
                data-testid="deleted-server-notice"
                className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card p-10 text-center"
            >
                <ServerOff className="mb-3 h-10 w-10 text-muted-foreground" aria-hidden="true" />
                <h1 className="text-lg font-semibold text-foreground">
                    {serverName ? (
                        <>
                            <span className="font-mono">{serverName}</span> has been deleted
                        </>
                    ) : (
                        "This server has been deleted"
                    )}
                </h1>
                <p className="mt-1 max-w-md text-sm text-muted-foreground">
                    Its execution history is kept, but the server, its tools and its connection settings are gone.
                </p>
                <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
                    <Button asChild variant="outline" size="sm" className="gap-1.5">
                        <Link href="/executions">
                            <History className="h-4 w-4" />
                            Execution History
                        </Link>
                    </Button>
                    <Button asChild size="sm" className="gap-1.5">
                        <Link href="/servers">
                            <Server className="h-4 w-4" />
                            Go to Servers
                        </Link>
                    </Button>
                </div>
            </div>
        </div>
    );
}
