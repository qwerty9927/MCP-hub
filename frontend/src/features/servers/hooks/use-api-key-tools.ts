import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { authApi } from "@/lib/api";
import { AppApiError } from "@/lib/errors";
import { ApiKeyTool } from "@/types";
import { SERVERS_QUERY_KEY } from "./use-servers";

/**
 * Lives under the server's "tools" key so that refreshing or connecting the server (which re-discovers its
 * tools) also refetches what each API key sees.
 */
export function apiKeyServerToolsQueryKey(keyId: string | null, serverId: string) {
    return [...SERVERS_QUERY_KEY, serverId, "tools", "api-key", keyId];
}

/** The server's tools with whether each is visible to the API key. Runs only once a key is chosen. */
export function useApiKeyServerTools(keyId: string | null, serverId: string) {
    return useQuery({
        queryKey: apiKeyServerToolsQueryKey(keyId, serverId),
        queryFn: ({ signal }) => authApi.listServerTools(keyId as string, serverId, signal),
        enabled: Boolean(keyId && serverId),
    });
}

interface SetToolEnabledVariables {
    toolName: string;
    enabled: boolean;
}

/** Show or hide one tool for the API key. Updates the list at once and rolls back if the server refuses. */
export function useSetApiKeyToolEnabled(keyId: string | null, serverId: string) {
    const queryClient = useQueryClient();
    const queryKey = apiKeyServerToolsQueryKey(keyId, serverId);

    return useMutation({
        mutationFn: ({ toolName, enabled }: SetToolEnabledVariables) =>
            authApi.setToolEnabled(keyId as string, serverId, toolName, enabled),
        onMutate: async ({ toolName, enabled }: SetToolEnabledVariables) => {
            await queryClient.cancelQueries({ queryKey });
            const previous = queryClient.getQueryData<ApiKeyTool[]>(queryKey);
            queryClient.setQueryData<ApiKeyTool[]>(queryKey, (tools) =>
                tools?.map((tool) => (tool.name === toolName ? { ...tool, enabled } : tool))
            );
            return { previous };
        },
        onError: (err: AppApiError, _variables, context) => {
            queryClient.setQueryData(queryKey, context?.previous);
            toast.error(err.message || "Failed to change tool visibility");
        },
        onSettled: () => queryClient.invalidateQueries({ queryKey }),
    });
}
