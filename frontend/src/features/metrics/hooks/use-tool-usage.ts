import { useQuery } from "@tanstack/react-query";
import { executionsApi } from "@/lib/api";
import { UsageRange } from "@/types";
import { EXECUTIONS_QUERY_KEY } from "@/features/executions/hooks/use-executions";

export function useToolUsage(range: UsageRange, limit = 10) {
    return useQuery({
        queryKey: [...EXECUTIONS_QUERY_KEY, "tool-usage", range, limit],
        queryFn: ({ signal }) => executionsApi.toolUsage({ range, limit }, signal),
    });
}
