"use client";

import React, { useEffect, useSyncExternalStore } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { AUTH_CHANGED_EVENT, clearAuthToken, getAuthToken, loginPath } from "@/lib/auth-token";
import { useMe } from "@/features/auth/hooks/use-auth";

function subscribe(onChange: () => void) {
    window.addEventListener(AUTH_CHANGED_EVENT, onChange);
    window.addEventListener("storage", onChange);
    return () => {
        window.removeEventListener(AUTH_CHANGED_EVENT, onChange);
        window.removeEventListener("storage", onChange);
    };
}

/** Renders the dashboard only for a signed-in account; otherwise sends the user to the login page. */
export function AuthGuard({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();
    const token = useSyncExternalStore(subscribe, getAuthToken, () => null);
    const { data: me, isError } = useMe(Boolean(token));

    useEffect(() => {
        if (!token) {
            router.replace(loginPath(pathname ?? undefined));
        } else if (isError) {
            clearAuthToken();
        }
    }, [token, isError, pathname, router]);

    if (!token || !me) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-background" role="status" aria-label="Checking sign-in">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }
    return <>{children}</>;
}
