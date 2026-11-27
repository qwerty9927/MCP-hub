import { useQuery } from "@tanstack/react-query";
import { executionsApi } from "@/lib/api";
import { UsageRange } from "@/types";
import { EXECUTIONS_QUERY_KEY } from "@/features/executions/hooks/use-executions";

/** Calls per time bucket over `range`; with `serverId`, only that Server's calls. */
export function useCallsTimeseries(range: UsageRange, serverId?: string) {
    return useQuery({
        queryKey: [...EXECUTIONS_QUERY_KEY, "timeseries", range, serverId ?? null],
        queryFn: ({ signal }) => executionsApi.timeseries(serverId ? { range, server_id: serverId } : { range }, signal),
    });
}
