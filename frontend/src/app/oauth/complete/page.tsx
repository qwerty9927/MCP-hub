"use client";

import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { completionRedirect, readCompletionMessage } from "@/lib/oauth-complete";

/**
 * The backend's OAuth callback redirects the sign-in popup here. The page hands the outcome to the window that
 * opened it (same origin only, via the postMessage target origin) and closes. Opened without a popup — the
 * "Continue in this tab" fallback — it redirects to the new server, or to the servers list with the error.
 */
export default function OAuthCompletePage() {
    const [stuck, setStuck] = useState(false);

    useEffect(() => {
        const message = readCompletionMessage(window.location.search);
        const opener = window.opener as Window | null;

        if (opener && !opener.closed) {
            try {
                // The target origin restricts delivery to an opener on this same origin.
                opener.postMessage(message, window.location.origin);
                window.close();
                // Some browsers refuse to close the window; tell the user it's safe to close it themselves.
                const timer = window.setTimeout(() => setStuck(true), 500);
                return () => window.clearTimeout(timer);
            } catch {
                // Fall through to the full-page redirect.
            }
        }
        window.location.replace(completionRedirect(message));
    }, []);

    return (
        <main className="flex min-h-screen items-center justify-center bg-background p-6">
            <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                {stuck ? (
                    "Sign-in finished. You can close this window."
                ) : (
                    <>
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                        Finishing sign-in…
                    </>
                )}
            </p>
        </main>
    );
}
