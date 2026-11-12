"use client";

import React from "react";
import { Menu, ExternalLink, ShieldCheck, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/common/ThemeToggle";
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
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
    const docsUrl = apiBaseUrl.replace(/\/api\/v1\/?$/, "/docs");

    return (
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-background/95 backdrop-blur px-4 sm:px-6">
            <div className="flex items-center gap-2">
                <Button variant="ghost" size="icon" onClick={onMenuToggle} className="md:hidden">
                    <Menu className="h-5 w-5" />
                    <span className="sr-only">Toggle Sidebar</span>
                </Button>
            </div>

            <div className="flex items-center gap-3">
                {/* API Docs Link */}
                <Button asChild variant="outline" size="sm" className="hidden sm:inline-flex gap-1.5 h-8 text-xs font-medium">
                    <a href={docsUrl} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-3.5 w-3.5" />
                        Swagger Docs
                    </a>
                </Button>

                {/* Theme Switcher */}
                <ThemeToggle />

                {/* Account Menu */}
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="flex items-center gap-2 h-9 px-2">
                            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary">
                                <User className="h-4 w-4" />
                            </div>
                            <span className="hidden sm:inline-block text-xs font-medium text-foreground">Admin</span>
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-56">
                        <DropdownMenuLabel className="font-normal">
                            <div className="flex flex-col space-y-1">
                                <p className="text-sm font-medium leading-none">Administrator</p>
                                <p className="text-xs leading-none text-muted-foreground flex items-center gap-1 mt-1">
                                    <ShieldCheck className="h-3 w-3 text-emerald-500" />
                                    Full System Access
                                </p>
                            </div>
                        </DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem asChild>
                            <a
                                href={docsUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center justify-between w-full cursor-pointer"
                            >
                                <span>Interactive OpenAPI</span>
                                <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                            </a>
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem disabled className="text-xs text-muted-foreground">
                            Backend: {apiBaseUrl}
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </header>
    );
}
