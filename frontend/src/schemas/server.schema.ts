import { z } from "zod";

export const serverFormSchema = z
    .object({
        name: z
            .string()
            .min(1, "Server name is required")
            .max(100, "Server name cannot exceed 100 characters")
            .regex(
                /^[a-zA-Z0-9_\-\.]+$/,
                "Name can only contain alphanumeric characters, hyphens, underscores, and dots"
            ),
        description: z
            .string()
            .max(500, "Description cannot exceed 500 characters")
            .optional()
            .or(z.literal("")),
        transport: z.enum(["stdio", "streamable-http"]),
        enabled: z.boolean().default(true),

        // Stdio fields
        stdio_command: z.string().optional().or(z.literal("")),
        stdio_args: z.string().optional().or(z.literal("")),
        stdio_env: z.string().optional().or(z.literal("")),

        // HTTP fields
        http_url: z.string().optional().or(z.literal("")),
        http_headers: z.string().optional().or(z.literal("")),
    })
    .superRefine((data, ctx) => {
        if (data.transport === "stdio") {
            if (!data.stdio_command || data.stdio_command.trim().length === 0) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: ["stdio_command"],
                    message: "Command executable is required for stdio transport (e.g. 'python3')",
                });
            }
        } else if (data.transport === "streamable-http") {
            if (!data.http_url || data.http_url.trim().length === 0) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: ["http_url"],
                    message: "Endpoint URL is required for streamable-http transport",
                });
            } else {
                try {
                    const parsed = new URL(data.http_url);
                    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
                        ctx.addIssue({
                            code: z.ZodIssueCode.custom,
                            path: ["http_url"],
                            message: "URL protocol must be http:// or https://",
                        });
                    }
                } catch {
                    ctx.addIssue({
                        code: z.ZodIssueCode.custom,
                        path: ["http_url"],
                        message: "Must be a valid URL (e.g. 'http://localhost:8000/mcp')",
                    });
                }
            }
        }
    });

export type ServerFormValues = z.infer<typeof serverFormSchema>;
