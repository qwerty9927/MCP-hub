/**
 * Links to a server from execution history. The server may have been deleted since (its id is kept on the
 * execution), so the link tells the server page where the user came from and the name to show.
 */
export function historyServerHref(serverId: string, serverName: string): string {
    const params = new URLSearchParams({ from: "history", name: serverName });
    return `/servers/${encodeURIComponent(serverId)}?${params.toString()}`;
}

/** Reads what `historyServerHref` put on the server page's URL. */
export function readHistoryOrigin(search: URLSearchParams | null): { fromHistory: boolean; serverName: string | null } {
    return { fromHistory: search?.get("from") === "history", serverName: search?.get("name") || null };
}
