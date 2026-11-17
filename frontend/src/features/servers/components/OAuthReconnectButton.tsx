"use client";

import React, { useState } from "react";
import { KeyRound } from "lucide-react";
import { Button, ButtonProps } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { ServerRead } from "@/types";
import { useOAuthFlow, useOAuthProviders } from "../hooks/use-oauth";
import { OAuthConnectPanel } from "./OAuthConnectPanel";

interface OAuthReconnectButtonProps extends Omit<ButtonProps, "onClick" | "asChild"> {
    server: ServerRead;
}

/** Signs in to an OAuth server's provider again (same popup flow as Register Server). */
export function OAuthReconnectButton({ server, className, size = "sm", ...props }: OAuthReconnectButtonProps) {
    const [open, setOpen] = useState(false);
    const flow = useOAuthFlow();
    const { data: providers } = useOAuthProviders(Boolean(server.oauth_provider_id));
    const provider = providers?.find((item) => item.id === server.oauth_provider_id);
    const tileProvider = { name: provider?.name ?? server.name, logo: provider?.logo ?? null };

    const start = () => {
        setOpen(true);
        void flow.reconnect(server.id);
    };

    const close = () => {
        flow.reset();
        setOpen(false);
    };

    return (
        <>
            <Button {...props} size={size} onClick={start} className={cn("gap-1.5", className)}>
                <KeyRound className="h-4 w-4" aria-hidden="true" />
                Reconnect
            </Button>
            <Dialog open={open} onOpenChange={(next) => (next ? setOpen(true) : close())}>
                <DialogContent className="max-w-md">
                    <DialogHeader className="text-left">
                        <DialogTitle>Reconnect {server.name}</DialogTitle>
                        <DialogDescription>Sign in to {tileProvider.name} again so the hub can keep using this server.</DialogDescription>
                    </DialogHeader>
                    <OAuthConnectPanel
                        provider={tileProvider}
                        state={flow.state}
                        toolCount={null}
                        onCancel={close}
                        onReopen={flow.reopen}
                        onContinueInTab={flow.continueInTab}
                        onRetry={() => void flow.reconnect(server.id)}
                        onOpenServer={close}
                        successActionLabel="Done"
                    />
                </DialogContent>
            </Dialog>
        </>
    );
}
