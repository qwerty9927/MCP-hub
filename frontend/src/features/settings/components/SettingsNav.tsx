"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import { SETTINGS_GROUPS } from "../sections";

/** Section nav for Settings: User and Hub scopes. A row of pills on narrow screens, a column beside the content on wide ones. */
export function SettingsNav({ className }: { className?: string }) {
    const pathname = usePathname();
    return (
        <nav aria-label="Settings" className={cn("flex flex-col gap-4", className)}>
            {SETTINGS_GROUPS.map((group) => (
                <div key={group.label} className="flex flex-col gap-1">
                    <span className="px-2.5 text-xs font-medium text-muted-foreground">{group.label}</span>
                    <ul className="flex flex-wrap gap-1 lg:flex-col">
                        {group.sections.map((section) => {
                            const active = pathname === section.href;
                            return (
                                <li key={section.href}>
                                    <Link
                                        href={section.href}
                                        aria-current={active ? "page" : undefined}
                                        aria-label={section.pending ? `${section.label} (backend pending)` : undefined}
                                        className={cn(
                                            "flex min-h-9 items-center gap-2 rounded-md px-2.5 text-[13px] transition-colors",
                                            active ? "bg-accent font-semibold text-primary" : "font-medium text-foreground hover:bg-accent"
                                        )}
                                    >
                                        <span className="flex-1">{section.label}</span>
                                        {section.pending && <Clock className="h-3 w-3 text-muted-foreground" aria-hidden="true" />}
                                    </Link>
                                </li>
                            );
                        })}
                    </ul>
                </div>
            ))}
        </nav>
    );
}
