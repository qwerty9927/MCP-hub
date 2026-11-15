"use client";

import React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLogin } from "@/features/auth/hooks/use-auth";
import { safeNextPath } from "@/lib/auth-token";
import { LoginFormValues, loginSchema } from "@/schemas/auth.schema";

export function LoginForm() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const login = useLogin();
    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });

    const onSubmit = handleSubmit(async (values) => {
        try {
            await login.mutateAsync(values);
            router.replace(safeNextPath(searchParams.get("next")));
        } catch {
            // Shown below from login.error
        }
    });

    return (
        <Card>
            <CardHeader>
                <CardTitle>Sign in</CardTitle>
                <CardDescription>Use your hub account to manage servers and sessions.</CardDescription>
            </CardHeader>
            <CardContent>
                <form onSubmit={onSubmit} className="space-y-4" noValidate>
                    <div className="space-y-2">
                        <Label htmlFor="email">Email</Label>
                        <Input id="email" type="email" autoComplete="email" {...register("email")} />
                        {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="password">Password</Label>
                        <Input id="password" type="password" autoComplete="current-password" {...register("password")} />
                        {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
                    </div>
                    {login.error && (
                        <p role="alert" className="text-sm text-destructive">
                            {login.error.message}
                        </p>
                    )}
                    <Button type="submit" className="w-full" disabled={login.isPending}>
                        {login.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Sign in
                    </Button>
                    <p className="text-center text-xs text-muted-foreground">
                        No account?{" "}
                        <Link href="/register" className="font-medium text-primary hover:underline">
                            Create one
                        </Link>
                    </p>
                </form>
            </CardContent>
        </Card>
    );
}
