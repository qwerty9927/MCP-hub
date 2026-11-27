import React from "react";
import Link from "next/link";
import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface ActionTileProps {
    icon: LucideIcon;
    label: string;
    href?: string;
    onClick?: () => void;
    className?: string;
}

const TILE =
    "flex min-h-[88px] flex-1 items-center justify-center gap-2 rounded-lg border border-dashed border-input bg-muted px-4 text-sm font-medium text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** Dashed tile that fills an empty slot with one verb ("Register a server"). */
export function ActionTile({ icon: Icon, label, href, onClick, className }: ActionTileProps) {
    const content = (
        <>
            <Icon className="h-4 w-4" aria-hidden="true" />
            {label}
        </>
    );
    if (href) {
        return (
            <Link href={href} className={cn(TILE, className)}>
                {content}
            </Link>
        );
    }
    return (
        <button type="button" onClick={onClick} className={cn(TILE, className)}>
            {content}
        </button>
    );
}
