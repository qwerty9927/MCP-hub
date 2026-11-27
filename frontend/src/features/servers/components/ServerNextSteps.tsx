import React from "react";
import Link from "next/link";
import { ChevronRight, FileText, Plug, Play, SquareTerminal, LucideIcon } from "lucide-react";
import { API_DOCS_URL, SHOW_BACKEND_DETAILS } from "@/lib/config";

const MCP_SPEC_URL = "https://modelcontextprotocol.io";

interface Step {
    label: string;
    href: string;
    icon: LucideIcon;
    external?: boolean;
}

const CHIP =
    "inline-flex h-10 items-center gap-2 rounded-md border border-input px-3 text-sm font-medium text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** "What to do next" chips that close the server page. */
export function ServerNextSteps({ serverId }: { serverId: string }) {
    const steps: Step[] = [
        { label: "Test a Tool", href: `/playground?server=${serverId}`, icon: Play },
        { label: "Connect an Agent", href: "/settings/api-keys", icon: Plug },
        ...(SHOW_BACKEND_DETAILS ? [{ label: "Use the API", href: API_DOCS_URL, icon: SquareTerminal, external: true }] : []),
        { label: "Read the MCP Spec", href: MCP_SPEC_URL, icon: FileText, external: true },
    ];

    return (
        <section aria-labelledby="server-next" className="overflow-hidden rounded-xl border border-border bg-card">
            <h2 id="server-next" className="border-b border-border bg-muted px-5 py-3 text-sm font-semibold">
                What to do next
            </h2>
            <div className="flex flex-wrap gap-2.5 px-5 py-4">
                {steps.map((step) => {
                    const Icon = step.icon;
                    const content = (
                        <>
                            <Icon className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                            {step.label}
                            <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
                        </>
                    );
                    return step.external ? (
                        <a key={step.label} href={step.href} target="_blank" rel="noopener noreferrer" className={CHIP}>
                            {content}
                            <span className="sr-only">(opens in a new tab)</span>
                        </a>
                    ) : (
                        <Link key={step.label} href={step.href} className={CHIP}>
                            {content}
                        </Link>
                    );
                })}
            </div>
        </section>
    );
}
