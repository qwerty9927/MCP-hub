"use client";

import React, { useEffect, useState } from "react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { AuthGuard } from "./AuthGuard";
import { QuickSearchDialog } from "./QuickSearchDialog";
import { usePreferences } from "@/lib/use-preferences";
import { X } from "lucide-react";

interface DashboardShellProps {
    children: React.ReactNode;
}

export function DashboardShell({ children }: DashboardShellProps) {
    const [mobileOpen, setMobileOpen] = useState(false);
    const [searchOpen, setSearchOpen] = useState(false);
    // The dialog (and its queries) mounts on first use.
    const [searchUsed, setSearchUsed] = useState(false);
    const [preferences] = usePreferences();

    const openSearch = () => {
        setMobileOpen(false);
        setSearchUsed(true);
        setSearchOpen(true);
    };

    // ⌘K / Ctrl+K opens quick search, unless keyboard shortcuts are turned off in Settings.
    useEffect(() => {
        if (!preferences.keyboardShortcuts) return;
        const onKeyDown = (event: KeyboardEvent) => {
            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
                event.preventDefault();
                setSearchUsed(true);
                setSearchOpen((open) => !open);
            }
        };
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [preferences.keyboardShortcuts]);

    return (
        <AuthGuard>
            <div className="flex min-h-screen bg-background">
                {/* Desktop Fixed Sidebar */}
                <aside className="hidden md:fixed md:inset-y-0 md:z-40 md:flex md:w-64 md:flex-col">
                    <Sidebar onOpenSearch={openSearch} />
                </aside>

                {/* Mobile Drawer Overlay */}
                {mobileOpen && (
                    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm md:hidden" onClick={() => setMobileOpen(false)} />
                )}

                {/* Mobile Drawer Sidebar */}
                <div
                    className={`fixed inset-y-0 left-0 z-50 w-72 transform transition-transform duration-200 ease-in-out md:hidden ${
                        mobileOpen ? "translate-x-0" : "-translate-x-full"
                    }`}
                >
                    <div className="relative h-full">
                        <Sidebar onItemClick={() => setMobileOpen(false)} onOpenSearch={openSearch} className="pt-12" />
                        <button
                            onClick={() => setMobileOpen(false)}
                            className="absolute right-3 top-3 rounded-md p-1 text-muted-foreground hover:bg-muted"
                        >
                            <X className="h-5 w-5" />
                            <span className="sr-only">Close sidebar</span>
                        </button>
                    </div>
                </div>

                {/* Main Content Area */}
                <div className="flex min-w-0 flex-1 flex-col md:pl-64">
                    <Header onMenuToggle={() => setMobileOpen(!mobileOpen)} />
                    <main className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
                </div>
            </div>
            {searchUsed && <QuickSearchDialog open={searchOpen} onOpenChange={setSearchOpen} />}
        </AuthGuard>
    );
}
