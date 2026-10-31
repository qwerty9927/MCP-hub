"use client";

import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import { Toaster } from "sonner";

export function Providers({ children }: { children: React.ReactNode }) {
    const [queryClient] = React.useState(
        () =>
            new QueryClient({
                defaultOptions: {
                    queries: {
                        staleTime: 30 * 1000,
                        retry: (failureCount, error: any) => {
                            // Don't retry on 404 or 400 client errors
                            if (
                                error?.status === 404 ||
                                error?.status === 400 ||
                                error?.status === 422
                            ) {
                                return false;
                            }
                            return failureCount < 2;
                        },
                        refetchOnWindowFocus: false,
                    },
                },
            })
    );

    return (
        <NextThemesProvider
            attribute="class"
            defaultTheme="system"
            enableSystem
            disableTransitionOnChange
        >
            <QueryClientProvider client={queryClient}>
                {children}
                <Toaster richColors position="top-right" closeButton />
            </QueryClientProvider>
        </NextThemesProvider>
    );
}
