import { useQuery } from "@tanstack/react-query";
import { executionsApi } from "@/lib/api";
import { ExecutionFilterParams } from "@/types";

export const EXECUTIONS_QUERY_KEY = ["executions"];

export function useExecutions(params?: ExecutionFilterParams) {
    return useQuery({
        queryKey: [...EXECUTIONS_QUERY_KEY, params],
        queryFn: () => executionsApi.list(params),
    });
}

export function useExecution(executionId: string) {
    return useQuery({
        queryKey: [...EXECUTIONS_QUERY_KEY, executionId],
        queryFn: () => executionsApi.getById(executionId),
        enabled: Boolean(executionId),
    });
}
