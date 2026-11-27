import React from "react";
import Link from "next/link";
import { ChevronRight, Plug, Play, LucideIcon } from "lucide-react";

interface Step {
    label: string;
    href: string;
    icon: LucideIcon;
}

const CHIP =
    "inline-flex h-10 items-center gap-2 rounded-md border border-input px-3 text-sm font-medium text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** "What to do next" chips that close the server page. */
export function ServerNextSteps({ serverId }: { serverId: string }) {
    const steps: Step[] = [
        { label: "Test a Tool", href: `/playground?server=${serverId}`, icon: Play },
        { label: "Connect an Agent", href: "/settings/api-keys", icon: Plug },
    ];

    return (
        <section aria-labelledby="server-next" className="overflow-hidden rounded-xl border border-border bg-card">
            <h2 id="server-next" className="border-b border-border bg-muted px-5 py-3 text-sm font-semibold">
                What to do next
            </h2>
            <div className="flex flex-wrap gap-2.5 px-5 py-4">
                {steps.map((step) => {
                    const Icon = step.icon;
                    return (
                        <Link key={step.label} href={step.href} className={CHIP}>
                            <Icon className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                            {step.label}
                            <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
                        </Link>
                    );
                })}
            </div>
        </section>
    );
}
