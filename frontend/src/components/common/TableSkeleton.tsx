"use client";

import React from "react";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

interface TableSkeletonProps {
    columns?: string[] | number;
    rowCount?: number;
    showPagination?: boolean;
}

export function TableSkeleton({
    columns = 5,
    rowCount = 5,
    showPagination = true,
}: TableSkeletonProps) {
    const columnHeaders = Array.isArray(columns)
        ? columns
        : Array.from({ length: columns }, (_, i) => `Column ${i + 1}`);

    const rows = Array.from({ length: rowCount }, (_, i) => i);

    return (
        <div className="space-y-4">
            <div className="rounded-md border border-border bg-card overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow>
                            {columnHeaders.map((col, idx) => (
                                <TableHead
                                    key={idx}
                                    className={idx === columnHeaders.length - 1 ? "text-right" : ""}
                                >
                                    <Skeleton className="h-4 w-20" />
                                </TableHead>
                            ))}
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {rows.map((rowIdx) => (
                            <TableRow key={rowIdx}>
                                {columnHeaders.map((_, colIdx) => (
                                    <TableCell
                                        key={colIdx}
                                        className={
                                            colIdx === columnHeaders.length - 1 ? "text-right" : ""
                                        }
                                    >
                                        {colIdx === 0 ? (
                                            <div className="space-y-1.5">
                                                <Skeleton className="h-4 w-32" />
                                                <Skeleton className="h-3 w-20" />
                                            </div>
                                        ) : colIdx === columnHeaders.length - 1 ? (
                                            <div className="flex justify-end gap-2">
                                                <Skeleton className="h-8 w-16 rounded-md" />
                                            </div>
                                        ) : colIdx === 2 ? (
                                            <Skeleton className="h-5 w-24 rounded-full" />
                                        ) : (
                                            <Skeleton className="h-4 w-24" />
                                        )}
                                    </TableCell>
                                ))}
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>

            {showPagination && (
                <div className="flex items-center justify-between px-2">
                    <Skeleton className="h-4 w-40" />
                    <div className="flex items-center gap-2">
                        <Skeleton className="h-8 w-20 rounded-md" />
                        <Skeleton className="h-8 w-20 rounded-md" />
                    </div>
                </div>
            )}
        </div>
    );
}
