import { z } from "zod";

export const loginSchema = z.object({
    email: z.string().trim().min(1, "Email is required"),
    password: z.string().min(1, "Password is required"),
});

export const registerSchema = z
    .object({
        email: z.string().trim().email("Enter a valid email address").max(255),
        password: z.string().min(8, "Use at least 8 characters").max(128, "Use at most 128 characters"),
        confirmPassword: z.string(),
    })
    .refine((data) => data.password === data.confirmPassword, {
        path: ["confirmPassword"],
        message: "Passwords do not match",
    });

export const DEFAULT_SESSION_IDLE_MINUTES = 30;
export const MIN_SESSION_IDLE_MINUTES = 1;
export const MAX_SESSION_IDLE_MINUTES = 1440;

/** An idle-timeout input: empty means "use the default"; otherwise whole minutes within the hub's bounds. */
export const sessionIdleMinutesField = z
    .string()
    .trim()
    .refine(
        (value) =>
            value === "" || (/^\d+$/.test(value) && Number(value) >= MIN_SESSION_IDLE_MINUTES && Number(value) <= MAX_SESSION_IDLE_MINUTES),
        `Whole minutes from ${MIN_SESSION_IDLE_MINUTES} to ${MAX_SESSION_IDLE_MINUTES}, or empty for the default`
    );

/** The API value for a validated idle-timeout input: null (default) when empty. */
export function parseIdleMinutes(value: string): number | null {
    const trimmed = value.trim();
    return trimmed === "" ? null : Number(trimmed);
}

export const apiKeySchema = z.object({
    name: z.string().trim().min(1, "Give the key a name").max(100, "At most 100 characters"),
    sessionIdleMinutes: sessionIdleMinutesField,
});

export type LoginFormValues = z.infer<typeof loginSchema>;
export type RegisterFormValues = z.infer<typeof registerSchema>;
export type ApiKeyFormValues = z.infer<typeof apiKeySchema>;
