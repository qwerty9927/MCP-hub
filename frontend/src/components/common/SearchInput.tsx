"use client";

import React from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface SearchInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> {
    value: string;
    onValueChange: (value: string) => void;
    /** Accessible name of the search box. */
    label: string;
    /** Accessible name of the clear (✕) button. */
    clearLabel?: string;
    /** Classes for the wrapper, which sets the width. */
    className?: string;
    inputClassName?: string;
}

/** A search box with a leading search icon and its own clear button (the browser's built-in one is hidden). */
export const SearchInput = React.forwardRef<HTMLInputElement, SearchInputProps>(
    ({ value, onValueChange, label, clearLabel = "Clear search", placeholder, className, inputClassName, ...props }, ref) => {
        const innerRef = React.useRef<HTMLInputElement | null>(null);

        const setRefs = (node: HTMLInputElement | null) => {
            innerRef.current = node;
            if (typeof ref === "function") ref(node);
            else if (ref) ref.current = node;
        };

        return (
            <div className={cn("relative w-full", className)}>
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                    {...props}
                    ref={setRefs}
                    type="search"
                    aria-label={label}
                    placeholder={placeholder ?? label}
                    value={value}
                    onChange={(event) => onValueChange(event.target.value)}
                    className={cn("h-9 pl-8 pr-8 [&::-webkit-search-cancel-button]:appearance-none", inputClassName)}
                />
                {value && (
                    <button
                        type="button"
                        aria-label={clearLabel}
                        onClick={() => {
                            onValueChange("");
                            innerRef.current?.focus();
                        }}
                        className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    >
                        <X className="h-4 w-4" />
                    </button>
                )}
            </div>
        );
    }
);
SearchInput.displayName = "SearchInput";
