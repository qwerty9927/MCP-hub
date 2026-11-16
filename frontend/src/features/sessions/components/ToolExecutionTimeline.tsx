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
            <div className="relative pl-6 sm:pl-8 space-y-3">
                {toolCalls.map((call, index) => {
                    const isSelected = selectedCallId === call.id;
                    const isLast = index === toolCalls.length - 1;

                    return (
                        <div key={call.id} className="relative">
                            {/* Connector: from this node's centre (top-4 + half of h-5 = 26px) to the next node's centre,
                                i.e. this item's height plus the space-y-3 gap. Same left offset and width as the node,
                                so the line runs exactly through every node's centre. */}
                            {!isLast && (
                                <span
                                    aria-hidden="true"
                                    data-testid="timeline-connector"
                                    className="absolute -left-6 sm:-left-8 top-[26px] flex h-[calc(100%+0.75rem)] w-5 justify-center"
                                >
                                    <span className="h-full w-0.5 bg-border" />
                                </span>
                            )}

                            {/* Timeline Node Dot (after the connector, so it paints on top of it) */}
                            <div
                                className={`absolute -left-6 sm:-left-8 top-4 flex h-5 w-5 items-center justify-center rounded-full border-2 bg-background text-[10px] font-mono font-bold transition-colors ${
                                    isSelected
                                        ? "border-primary text-primary"
                                        : call.status === "failed"
                                          ? "border-destructive text-destructive"
                                          : call.status === "rejected"
                                            ? "border-orange-500 text-orange-600"
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
