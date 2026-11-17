import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { serversApi } from "@/lib/api";
import { ServerCreate, ServerFilterParams, ServerUpdate } from "@/types";
import { AppApiError } from "@/lib/errors";

export const SERVERS_QUERY_KEY = ["servers"];

export function useServers(params?: ServerFilterParams) {
    return useQuery({
        queryKey: [...SERVERS_QUERY_KEY, params],
        queryFn: ({ signal }) => serversApi.list(params, signal),
    });
}

export function useServer(serverId: string) {
    return useQuery({
        queryKey: [...SERVERS_QUERY_KEY, serverId],
        queryFn: ({ signal }) => serversApi.getById(serverId, signal),
        enabled: Boolean(serverId),
    });
}

/** Every tool of the server (all pages), so the tools tab can count and search the full list. */
export function useServerTools(serverId: string) {
    return useQuery({
        queryKey: [...SERVERS_QUERY_KEY, serverId, "tools"],
        queryFn: async ({ signal }) => ({ items: await serversApi.getAllTools(serverId, signal) }),
        enabled: Boolean(serverId),
    });
}

export function useCreateServer() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (payload: ServerCreate) => serversApi.create(payload),
        onSuccess: (server) => {
            queryClient.invalidateQueries({ queryKey: SERVERS_QUERY_KEY });
            toast.success(`Server "${server.name}" registered successfully`);
        },
        onError: (err: AppApiError) => {
            toast.error(err.message || "Failed to register server");
        },
    });
}

export function useUpdateServer() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ id, payload }: { id: string; payload: ServerUpdate }) => serversApi.update(id, payload),
        onSuccess: (server) => {
            queryClient.invalidateQueries({ queryKey: SERVERS_QUERY_KEY });
            queryClient.setQueryData([...SERVERS_QUERY_KEY, server.id], server);
            toast.success(`Server "${server.name}" updated successfully`);
        },
        onError: (err: AppApiError) => {
            toast.error(err.message || "Failed to update server");
        },
    });
}

export function useDeleteServer() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (serverId: string) => serversApi.delete(serverId),
        onSuccess: (_, serverId) => {
            queryClient.invalidateQueries({ queryKey: SERVERS_QUERY_KEY });
            queryClient.removeQueries({ queryKey: [...SERVERS_QUERY_KEY, serverId] });
            queryClient.invalidateQueries({ queryKey: ["tools"] });
            toast.success("Server deleted successfully");
        },
        onError: (err: AppApiError) => {
            toast.error(err.message || "Failed to delete server");
        },
    });
}

export function useConnectServer() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (serverId: string) => serversApi.connect(serverId),
        // Connecting re-discovers the server's tools, giving them new ids. Awaiting the refetch keeps the
        // mutation pending until the new list is loaded, so the old (stale) rows stay disabled until then.
        onSuccess: async (server) => {
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: SERVERS_QUERY_KEY }),
                queryClient.invalidateQueries({ queryKey: ["tools"] }),
                queryClient.invalidateQueries({ queryKey: ["system-health"] }),
            ]);
            toast.success(`Connected to "${server.name}". ${server.discovered_tool_count} tools discovered.`);
        },
        onError: (err: AppApiError) => {
            toast.error(err.message || "Connection failed");
        },
    });
}

export function useDisconnectServer() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (serverId: string) => serversApi.disconnect(serverId),
        onSuccess: (server) => {
            queryClient.invalidateQueries({ queryKey: SERVERS_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: ["system-health"] });
            toast.info(`Disconnected from "${server.name}"`);
        },
        onError: (err: AppApiError) => {
            toast.error(err.message || "Disconnection failed");
        },
    });
}

export function useTestServerConnection() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (serverId: string) => serversApi.testConnection(serverId),
        onSuccess: (res) => {
            queryClient.invalidateQueries({ queryKey: SERVERS_QUERY_KEY });
            if (res.success) {
                toast.success(`Connection verified! Latency: ${res.latency_ms.toFixed(1)}ms, Tools: ${res.tools_count}`);
            } else {
                toast.error(`Connection test failed: ${res.message}`);
            }
        },
        onError: (err: AppApiError) => {
            toast.error(err.message || "Failed to test connection");
        },
    });
}

export function useRefreshServerTools() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (serverId: string) => serversApi.refreshTools(serverId),
        // A refresh replaces the server's tools, giving them new ids. Awaiting the refetch keeps the
        // mutation pending until the new list is loaded, so the old (stale) rows stay disabled until then.
        onSuccess: async (tools, serverId) => {
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: SERVERS_QUERY_KEY }),
                queryClient.invalidateQueries({ queryKey: [...SERVERS_QUERY_KEY, serverId, "tools"] }),
                queryClient.invalidateQueries({ queryKey: ["tools"] }),
            ]);
            toast.success(`Discovered ${tools.length} tools`);
        },
        onError: (err: AppApiError) => {
            toast.error(err.message || "Failed to refresh tools");
        },
    });
}
