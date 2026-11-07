import { useQuery } from "@tanstack/react-query";
import { executionsApi } from "@/lib/api";
import { ExecutionFilterParams } from "@/types";

export const EXECUTIONS_QUERY_KEY = ["executions"];

export function useExecutions(
    params?: ExecutionFilterParams,
    options?: { refetchInterval?: number | false }
) {
    return useQuery({
        queryKey: [...EXECUTIONS_QUERY_KEY, params],
        queryFn: ({ signal }) => executionsApi.list(params, signal),
        refetchInterval: options?.refetchInterval,
    });
}

export function useExecution(executionId: string) {
    return useQuery({
        queryKey: [...EXECUTIONS_QUERY_KEY, executionId],
        queryFn: ({ signal }) => executionsApi.getById(executionId, signal),
        enabled: Boolean(executionId),
    });
}
