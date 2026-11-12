import { useQuery } from "@tanstack/react-query";
import { sessionsApi } from "@/lib/api";
import { SessionFilterParams, SessionToolCallFilterParams } from "@/types";

export const SESSIONS_QUERY_KEY = ["sessions"];

export function useSessions(params?: SessionFilterParams, options?: { refetchInterval?: number | false }) {
    return useQuery({
        queryKey: [...SESSIONS_QUERY_KEY, params],
        queryFn: ({ signal }) => sessionsApi.list(params, signal),
        refetchInterval: options?.refetchInterval,
    });
}

export function useSession(sessionId: string) {
    return useQuery({
        queryKey: [...SESSIONS_QUERY_KEY, sessionId],
        queryFn: ({ signal }) => sessionsApi.getById(sessionId, signal),
        enabled: Boolean(sessionId),
    });
}

export function useSessionToolCalls(
    sessionId: string,
    params?: SessionToolCallFilterParams,
    options?: { refetchInterval?: number | false }
) {
    return useQuery({
        queryKey: [...SESSIONS_QUERY_KEY, sessionId, "tool-calls", params],
        queryFn: ({ signal }) => sessionsApi.listToolCalls(sessionId, params, signal),
        enabled: Boolean(sessionId),
        refetchInterval: options?.refetchInterval,
    });
}
