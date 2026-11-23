"use client";

import React, { useEffect, useRef, useSyncExternalStore } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { refreshSession } from "@/lib/api-client";
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

/**
 * Renders the dashboard only for a signed-in account; otherwise sends the user to the login page.
 * A tab that opens without an access token (a new tab, a reopened browser) first tries the refresh token cookie.
 * A token that goes away later (sign-out, a rejected refresh) goes straight to login: refreshing then would race the
 * logout request and could sign the user back in.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();
    const token = useSyncExternalStore(subscribe, getAuthToken, () => null);
    const { data: me, isError } = useMe(Boolean(token));
    const cookieCheck = useRef<"untried" | "pending" | "settled">("untried");

    useEffect(() => {
        // Read storage here rather than trusting `token`: on a hard load the first (hydration) render
        // uses the server snapshot, which is always null, and redirecting on that would sign the user out.
        if (getAuthToken()) {
            cookieCheck.current = "settled";
            if (isError) clearAuthToken();
            return;
        }
        if (cookieCheck.current === "pending") return;
        if (cookieCheck.current === "settled") {
            router.replace(loginPath(pathname ?? undefined));
            return;
        }
        cookieCheck.current = "pending";
        void refreshSession().then((refreshed) => {
            cookieCheck.current = "settled";
            if (!refreshed) router.replace(loginPath(pathname ?? undefined));
        });
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
