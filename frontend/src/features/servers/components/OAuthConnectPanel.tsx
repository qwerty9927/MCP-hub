"use client";

import React from "react";
import { CheckCircle2, ExternalLink, Loader2, ShieldAlert, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { OAuthProvider } from "@/types";
import { OAuthFlowState } from "../hooks/use-oauth";
import { ProviderTile } from "./ProviderCard";

interface OAuthConnectPanelProps {
    provider: Pick<OAuthProvider, "name" | "logo">;
    state: OAuthFlowState;
    /** Tools discovered on the connected server, once it has loaded. */
    toolCount?: number | null;
    onCancel: () => void;
    onReopen: () => void;
    onContinueInTab: () => void;
    onRetry: () => void;
    onOpenServer?: () => void;
    onManual?: () => void;
    /** Primary action on success; defaults to "Open server". */
    successActionLabel?: string;
}

/** The connecting → done / error step of an OAuth sign-in, shared by Register Server and Reconnect. */
export function OAuthConnectPanel({
    provider,
    state,
    toolCount,
    onCancel,
    onReopen,
    onContinueInTab,
    onRetry,
    onOpenServer,
    onManual,
    successActionLabel = "Open server",
}: OAuthConnectPanelProps) {
    const name = provider.name;

    let icon: React.ReactNode = <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />;
    let title: React.ReactNode;
    let detail: React.ReactNode = null;
    let actions: React.ReactNode;

    switch (state.status) {
        case "blocked":
            icon = <ShieldAlert className="h-5 w-5 text-amber-600 dark:text-amber-400" aria-hidden="true" />;
            title = "Your browser blocked the sign-in popup";
            detail = `Allow popups for this site and reopen it, or sign in to ${name} in this tab. You'll come back here afterwards.`;
            actions = (
                <>
                    <Button variant="outline" onClick={onCancel}>
                        Cancel
                    </Button>
                    <Button variant="outline" onClick={onReopen}>
                        Reopen popup
                    </Button>
                    <Button onClick={onContinueInTab} className="gap-1.5">
                        <ExternalLink className="h-4 w-4" />
                        Continue in this tab
                    </Button>
                </>
            );
            break;
        case "success":
            icon = <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />;
            title = (
                <>
                    {name} connected
                    {typeof toolCount === "number" && (
                        <span className="font-normal text-muted-foreground">
                            {" "}
                            · <span className="font-mono">{toolCount}</span> {toolCount === 1 ? "tool" : "tools"} discovered
                        </span>
                    )}
                </>
            );
            actions = onOpenServer && <Button onClick={onOpenServer}>{successActionLabel}</Button>;
            break;
        case "error":
            icon = <XCircle className="h-5 w-5 text-red-700 dark:text-red-400" aria-hidden="true" />;
            title = `Couldn't connect ${name}`;
            detail = <span className="text-red-700 dark:text-red-400">{state.error}</span>;
            actions = (
                <>
                    {onManual && (
                        <Button variant="outline" onClick={onManual}>
                            Configure manually
                        </Button>
                    )}
                    <Button onClick={onRetry}>Try again</Button>
                </>
            );
            break;
        case "starting":
            title = `Starting sign-in with ${name}…`;
            actions = (
                <Button variant="outline" onClick={onCancel}>
                    Cancel
                </Button>
            );
            break;
        default:
            title = `Finish signing in to ${name} in the popup window`;
            detail = "Keep this dialog open. It updates as soon as you approve access.";
            actions = (
                <>
                    <Button variant="outline" onClick={onCancel}>
                        Cancel
                    </Button>
                    <Button variant="link" onClick={onReopen} className="px-2">
                        Reopen popup
                    </Button>
                </>
            );
    }

    return (
        <div
            className="flex flex-col items-center gap-4 px-2 py-10 text-center"
            data-testid="oauth-connect-panel"
            data-status={state.status}
        >
            <ProviderTile provider={provider} size="lg" />
            <div className="space-y-1.5" role="status" aria-live="polite">
                <p className="flex items-center justify-center gap-2 text-sm font-semibold text-foreground">
                    {icon}
                    <span>{title}</span>
                </p>
                {detail && <p className="mx-auto max-w-sm text-sm text-muted-foreground">{detail}</p>}
            </div>
            {actions && <div className="flex flex-wrap items-center justify-center gap-2">{actions}</div>}
        </div>
    );
}
