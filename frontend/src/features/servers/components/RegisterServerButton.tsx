"use client";

import React, { useState } from "react";
import { Plus } from "lucide-react";
import { Button, ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { RegisterServerDialog } from "./RegisterServerDialog";

interface RegisterServerButtonProps extends Omit<ButtonProps, "onClick" | "asChild"> {
    /** Button text; defaults to "Register Server". */
    label?: string;
}

/** The "Register Server" trigger used across the dashboard; opens the provider picker dialog. */
export function RegisterServerButton({ label = "Register Server", className, ...props }: RegisterServerButtonProps) {
    const [open, setOpen] = useState(false);
    // The dialog (and its queries) mounts on first use, then stays mounted so it can animate closed.
    const [used, setUsed] = useState(false);

    return (
        <>
            <Button
                {...props}
                onClick={() => {
                    setUsed(true);
                    setOpen(true);
                }}
                className={cn("gap-1.5", className)}
            >
                <Plus className="h-4 w-4" aria-hidden="true" />
                {label}
            </Button>
            {used && <RegisterServerDialog open={open} onOpenChange={setOpen} />}
        </>
    );
}
