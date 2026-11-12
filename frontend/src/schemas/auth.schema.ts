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

export const apiKeySchema = z.object({
    name: z.string().trim().min(1, "Give the key a name").max(100, "At most 100 characters"),
});

export type LoginFormValues = z.infer<typeof loginSchema>;
export type RegisterFormValues = z.infer<typeof registerSchema>;
export type ApiKeyFormValues = z.infer<typeof apiKeySchema>;
