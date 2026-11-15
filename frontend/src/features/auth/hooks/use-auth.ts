import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { authApi } from "@/lib/api";
import { clearAuthToken, setAuthToken } from "@/lib/auth-token";
import { AppApiError } from "@/lib/errors";
import { LoginRequest, RegisterRequest } from "@/types";

export const ME_QUERY_KEY = ["auth", "me"];
export const API_KEYS_QUERY_KEY = ["auth", "api-keys"];

export function useMe(enabled = true) {
    return useQuery({
        queryKey: ME_QUERY_KEY,
        queryFn: ({ signal }) => authApi.me(signal),
        enabled,
        retry: false,
        staleTime: 5 * 60 * 1000,
    });
}

export function useLogin() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (payload: LoginRequest) => {
            const token = await authApi.login(payload);
            setAuthToken(token.access_token);
            return token;
        },
        onSuccess: () => {
            queryClient.clear();
        },
    });
}

export function useRegister() {
    const login = useLogin();
    return useMutation({
        mutationFn: async (payload: RegisterRequest) => {
            await authApi.register(payload);
            return login.mutateAsync(payload);
        },
    });
}

export function useLogout() {
    const queryClient = useQueryClient();
    return () => {
        clearAuthToken();
        queryClient.clear();
    };
}

export function useApiKeys() {
    return useQuery({
        queryKey: API_KEYS_QUERY_KEY,
        queryFn: ({ signal }) => authApi.listApiKeys(signal),
    });
}

export function useCreateApiKey() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ name, sessionIdleMinutes = null }: { name: string; sessionIdleMinutes?: number | null }) =>
            authApi.createApiKey(name, sessionIdleMinutes),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY });
        },
        onError: (err: AppApiError) => {
            toast.error(err.message || "Failed to create API key");
        },
    });
}

export function useUpdateApiKey() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ keyId, sessionIdleMinutes }: { keyId: string; sessionIdleMinutes: number | null }) =>
            authApi.updateApiKey(keyId, sessionIdleMinutes),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY });
            toast.success("Session idle timeout updated");
        },
        onError: (err: AppApiError) => {
            toast.error(err.message || "Failed to update API key");
        },
    });
}

export function useRevokeApiKey() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (keyId: string) => authApi.revokeApiKey(keyId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY });
            toast.success("API key revoked");
        },
        onError: (err: AppApiError) => {
            toast.error(err.message || "Failed to revoke API key");
        },
    });
}
