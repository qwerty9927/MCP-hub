import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { toolsApi } from "@/lib/api";
import { ToolExecuteRequest, ToolFilterParams } from "@/types";
import { AppApiError } from "@/lib/errors";

export const TOOLS_QUERY_KEY = ["tools"];

export function useTools(params?: ToolFilterParams) {
    return useQuery({
        queryKey: [...TOOLS_QUERY_KEY, params],
        queryFn: () => toolsApi.list(params),
    });
}

export function useTool(toolId: string) {
    return useQuery({
        queryKey: [...TOOLS_QUERY_KEY, toolId],
        queryFn: () => toolsApi.getById(toolId),
        enabled: Boolean(toolId),
    });
}

export function useExecuteTool() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            serverId,
            toolName,
            payload,
        }: {
            serverId: string;
            toolName: string;
            payload: ToolExecuteRequest;
        }) => toolsApi.execute(serverId, toolName, payload),
        onSuccess: (res) => {
            queryClient.invalidateQueries({ queryKey: ["executions"] });
            queryClient.invalidateQueries({ queryKey: ["system-metrics"] });
            if (res.is_error) {
                toast.error(
                    `Tool execution completed with error (${res.duration_ms.toFixed(1)}ms)`
                );
            } else {
                toast.success(`Tool executed successfully in ${res.duration_ms.toFixed(1)}ms`);
            }
        },
        onError: (err: AppApiError) => {
            toast.error(err.message || "Execution request failed");
        },
    });
}
