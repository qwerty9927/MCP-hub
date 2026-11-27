import { useQuery } from "@tanstack/react-query";
import { executionsApi } from "@/lib/api";
import { UsageRange } from "@/types";
import { EXECUTIONS_QUERY_KEY } from "@/features/executions/hooks/use-executions";

/** Most-called tools over `range`; with `serverId`, only that Server's tools and calls. */
export function useToolUsage(range: UsageRange, limit = 10, serverId?: string) {
    return useQuery({
        queryKey: [...EXECUTIONS_QUERY_KEY, "tool-usage", range, limit, serverId ?? null],
        queryFn: ({ signal }) => executionsApi.toolUsage(serverId ? { range, limit, server_id: serverId } : { range, limit }, signal),
    });
}
