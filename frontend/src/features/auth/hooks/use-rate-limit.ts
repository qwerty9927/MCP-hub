import { useEffect, useMemo, useState } from "react";
import { isRateLimited } from "@/lib/errors";
import { formatRetryAfter } from "@/lib/utils";

const TICK_MS = 1000;

export interface AuthFormErrorState {
    /** What to show under the form; null when there is nothing to show. */
    message: string | null;
    /** True while a 429's Retry-After has not run out: submitting again would only be refused. */
    isLocked: boolean;
}

/**
 * The error to show on a sign-in or sign-up form. A 429 shows a countdown from its Retry-After and locks the form
 * until it runs out, then the error clears; any other error shows the backend's message.
 */
export function useAuthFormError(error: unknown): AuthFormErrorState {
    const lockedUntil = useMemo(() => {
        if (!isRateLimited(error) || error.retryAfterSeconds === undefined) return null;
        return Date.now() + error.retryAfterSeconds * TICK_MS;
    }, [error]);
    const [now, setNow] = useState(() => Date.now());

    useEffect(() => {
        if (lockedUntil === null) return;
        setNow(Date.now());
        const id = setInterval(() => {
            const current = Date.now();
            setNow(current);
            if (current >= lockedUntil) clearInterval(id);
        }, TICK_MS);
        return () => clearInterval(id);
    }, [lockedUntil]);

    if (!error) return { message: null, isLocked: false };
    if (isRateLimited(error) && lockedUntil !== null) {
        const secondsLeft = Math.ceil((lockedUntil - now) / TICK_MS);
        if (secondsLeft <= 0) return { message: null, isLocked: false };
        return { message: `Too many attempts. Try again in ${formatRetryAfter(secondsLeft)}.`, isLocked: true };
    }
    return { message: error instanceof Error ? error.message : "Something went wrong", isLocked: false };
}
