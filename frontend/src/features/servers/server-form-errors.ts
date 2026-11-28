import { AppApiError } from "@/lib/errors";
import { TransportType } from "@/types";

/** Form fields a backend error can be shown under. */
export type ServerFormField = "name" | "description" | "stdio_command" | "stdio_args" | "stdio_env" | "http_url" | "http_headers";

export interface ServerFieldError {
    field: ServerFormField;
    message: string;
}

/** What the backend shows in place of a saved credential header; sending it back keeps the saved value. */
export const MASKED_HEADER_VALUE = "********";

const HTTP_FORBIDDEN = 403;
const HTTP_CONFLICT = 409;

/** Request validation (422 with a list of {loc, msg}): the last loc segment names the field. */
const VALIDATION_LOC_FIELDS: Record<string, ServerFormField> = {
    name: "name",
    description: "description",
    command: "stdio_command",
    args: "stdio_args",
    env: "stdio_env",
    stdio_config: "stdio_command",
    url: "http_url",
    headers: "http_headers",
    http_config: "http_url",
};

/**
 * Policy refusals (403) and the masked-header check (422) put what they refused in `details`; the first key
 * present names the field. `argument` comes before `executable` because a refused flag carries both.
 */
const REFUSAL_DETAIL_FIELDS: ReadonlyArray<[string, ServerFormField]> = [
    ["header", "http_headers"],
    ["name", "stdio_env"],
    ["argument", "stdio_args"],
    ["executable", "stdio_command"],
    ["url", "http_url"],
];

interface ValidationItem {
    loc?: unknown[];
    msg?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validationFieldErrors(items: ValidationItem[]): ServerFieldError[] {
    return items.flatMap((item) => {
        const last = item.loc?.[item.loc.length - 1];
        const field = typeof last === "string" ? VALIDATION_LOC_FIELDS[last] : undefined;
        return field ? [{ field, message: item.msg ?? "Invalid value" }] : [];
    });
}

/** The form fields a failed create or update should mark, from the backend's error. */
export function serverFieldErrors(error: unknown, transport: TransportType): ServerFieldError[] {
    if (!(error instanceof AppApiError)) return [];
    const { details, message, status } = error;

    if (Array.isArray(details)) return validationFieldErrors(details as ValidationItem[]);
    if (status === HTTP_CONFLICT && isRecord(details) && "name" in details) return [{ field: "name", message }];
    if (isRecord(details)) {
        const match = REFUSAL_DETAIL_FIELDS.find(([key]) => key in details);
        if (match) return [{ field: match[1], message }];
    }
    // No details: e.g. stdio servers turned off on this hub (ALLOW_STDIO_SERVERS=false)
    if (status === HTTP_FORBIDDEN && transport === "stdio") return [{ field: "stdio_command", message }];
    return [];
}
