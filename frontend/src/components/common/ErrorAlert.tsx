import React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorAlertProps {
    title?: string;
    message: string;
    correlationId?: string;
    onRetry?: () => void;
    className?: string;
}

export function ErrorAlert({ title = "Failed to load data", message, correlationId, onRetry, className }: ErrorAlertProps) {
    return (
        <div className={cn("rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-destructive dark:text-red-400", className)}>
            <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" />
                <div className="flex-1 space-y-1">
                    <h4 className="font-semibold text-sm leading-none">{title}</h4>
                    <p className="text-sm opacity-90">{message}</p>
                    {correlationId && <p className="text-xs font-mono opacity-70">Correlation ID: {correlationId}</p>}
                </div>
                {onRetry && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onRetry}
                        className="shrink-0 border-destructive/40 hover:bg-destructive/20 text-destructive dark:text-red-300"
                    >
                        <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                        Retry
                    </Button>
                )}
            </div>
        </div>
    );
}
