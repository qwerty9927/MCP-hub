"use client";

import React from "react";
import { Menu, ExternalLink, LogOut, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { useLogout, useMe } from "@/features/auth/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/common/ThemeToggle";
import { API_BASE_URL, API_DOCS_URL, SHOW_API_DOCS } from "@/lib/config";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface HeaderProps {
    onMenuToggle?: () => void;
}

export function Header({ onMenuToggle }: HeaderProps) {
    const { data: me } = useMe();
    const logout = useLogout();
    const router = useRouter();

    const handleSignOut = () => {
        void logout();
        router.replace("/login");
    };

    return (
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-background/95 backdrop-blur px-4 sm:px-6">
            <div className="flex items-center gap-2">
                <Button variant="ghost" size="icon" onClick={onMenuToggle} className="md:hidden">
                    <Menu className="h-5 w-5" />
                    <span className="sr-only">Toggle Sidebar</span>
                </Button>
            </div>

            <div className="flex items-center gap-3">
                {/* API Docs Link (the backend hides its docs in production) */}
                {SHOW_API_DOCS && (
                    <Button asChild variant="outline" size="sm" className="hidden sm:inline-flex gap-1.5 h-8 text-xs font-medium">
                        <a href={API_DOCS_URL} target="_blank" rel="noopener noreferrer">
                            <ExternalLink className="h-3.5 w-3.5" />
                            Swagger Docs
                        </a>
                    </Button>
                )}

                {/* Theme Switcher */}
                <ThemeToggle />

                {/* Account Menu */}
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="flex items-center gap-2 h-9 px-2">
                            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary">
                                <User className="h-4 w-4" />
                            </div>
                            <span className="hidden sm:inline-block max-w-[180px] truncate text-xs font-medium text-foreground">
                                {me?.email ?? "Account"}
                            </span>
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-56">
                        <DropdownMenuLabel className="font-normal">
                            <div className="flex flex-col space-y-1">
                                <p className="text-xs leading-none text-muted-foreground">Signed in as</p>
                                <p className="text-sm font-medium leading-none truncate">{me?.email ?? "—"}</p>
                            </div>
                        </DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        {SHOW_API_DOCS && (
                            <>
                                <DropdownMenuItem asChild>
                                    <a
                                        href={API_DOCS_URL}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center justify-between w-full cursor-pointer"
                                    >
                                        <span>Interactive OpenAPI</span>
                                        <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                                    </a>
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                            </>
                        )}
                        <DropdownMenuItem disabled className="text-xs text-muted-foreground">
                            Backend: {API_BASE_URL}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onSelect={handleSignOut} className="cursor-pointer gap-2">
                            <LogOut className="h-3.5 w-3.5" />
                            Sign out
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </header>
    );
}
