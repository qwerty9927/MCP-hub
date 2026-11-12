import React from "react";
import { Cpu } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
    return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-10">
            <div className="mb-6 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
                    <Cpu className="h-5 w-5" />
                </div>
                <span className="text-lg font-bold tracking-tight text-foreground">MCP Hub</span>
            </div>
            <div className="w-full max-w-sm">{children}</div>
        </div>
    );
}
