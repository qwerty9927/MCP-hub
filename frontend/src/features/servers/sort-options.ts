import { ServerSortField, SortOrder } from "@/types";

export interface ServerSortOption {
    /** The Select item's value; only used to find the option again. */
    value: string;
    label: string;
    sort_by: ServerSortField;
    sort_order: SortOrder;
}

/** The server list's sort choices; each sort_by must be one GET /servers accepts (anything else is a 422). */
export const SERVER_SORT_OPTIONS: readonly ServerSortOption[] = [
    { value: "newest", label: "Newest First", sort_by: "created_at", sort_order: "desc" },
    { value: "oldest", label: "Oldest First", sort_by: "created_at", sort_order: "asc" },
    { value: "name-asc", label: "Name (A-Z)", sort_by: "name", sort_order: "asc" },
    { value: "name-desc", label: "Name (Z-A)", sort_by: "name", sort_order: "desc" },
    { value: "updated", label: "Recently Updated", sort_by: "updated_at", sort_order: "desc" },
];

export const DEFAULT_SERVER_SORT = SERVER_SORT_OPTIONS[0];

/** The option matching a sort, else the default (newest first), which is also what the backend does without one. */
export function findServerSortOption(sortBy?: ServerSortField, sortOrder?: SortOrder): ServerSortOption {
    const field = sortBy ?? DEFAULT_SERVER_SORT.sort_by;
    const order = sortOrder ?? DEFAULT_SERVER_SORT.sort_order;
    return SERVER_SORT_OPTIONS.find((option) => option.sort_by === field && option.sort_order === order) ?? DEFAULT_SERVER_SORT;
}
