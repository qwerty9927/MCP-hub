"use client";

import React from "react";
import { History } from "lucide-react";
import { ToolCallRead } from "@/types";
import { ToolCallItem } from "./ToolCallItem";
import { EmptyState } from "@/components/common/EmptyState";

interface ToolExecutionTimelineProps {
    toolCalls: ToolCallRead[];
    selectedCallId?: string | null;
    onSelectCall: (call: ToolCallRead) => void;
}

export function ToolExecutionTimeline({ toolCalls, selectedCallId, onSelectCall }: ToolExecutionTimelineProps) {
    if (toolCalls.length === 0) {
        return (
            <EmptyState
                icon={History}
                title="No tool executions found"
                description="This session does not have any tool calls matching your current filter criteria."
            />
        );
    }

    return (
        <div className="relative space-y-4">
            {/* Timeline connector track */}
            <div className="relative pl-6 sm:pl-8 space-y-3 before:absolute before:left-2.5 sm:before:left-3 before:top-3 before:bottom-3 before:w-0.5 before:bg-border">
                {toolCalls.map((call, index) => {
                    const isSelected = selectedCallId === call.id;

                    return (
                        <div key={call.id} className="relative">
                            {/* Timeline Node Dot */}
                            <div
                                className={`absolute -left-6 sm:-left-8 top-4 flex h-5 w-5 items-center justify-center rounded-full border-2 bg-background text-[10px] font-mono font-bold transition-colors ${
                                    isSelected
                                        ? "border-primary text-primary"
                                        : call.status === "failed"
                                          ? "border-destructive text-destructive"
                                          : call.status === "running"
                                            ? "border-amber-500 text-amber-600"
                                            : "border-muted-foreground/40 text-muted-foreground"
                                }`}
                            >
                                {index + 1}
                            </div>

                            <ToolCallItem call={call} isSelected={isSelected} onSelect={onSelectCall} />
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
