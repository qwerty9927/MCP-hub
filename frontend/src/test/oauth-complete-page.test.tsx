import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";
import React from "react";
import OAuthCompletePage from "@/app/oauth/complete/page";
import { completionRedirect, readCompletionMessage } from "@/lib/oauth-complete";

describe("readCompletionMessage / completionRedirect", () => {
    it("reads a success redirect", () => {
        const message = readCompletionMessage("?status=success&server_id=srv-1");
        expect(message).toEqual({ type: "mcp-hub-oauth", status: "success", server_id: "srv-1", error: null });
        expect(completionRedirect(message)).toBe("/servers/srv-1");
    });

    it("reads an error redirect", () => {
        const message = readCompletionMessage("?status=error&error=access_denied");
        expect(message).toEqual({ type: "mcp-hub-oauth", status: "error", server_id: null, error: "access_denied" });
        expect(completionRedirect(message)).toBe("/servers?oauth_error=access_denied");
    });

    it("treats anything else as an error", () => {
        const message = readCompletionMessage("");
        expect(message.status).toBe("error");
        expect(completionRedirect(message)).toBe("/servers?oauth_error=unknown_error");
    });
});

describe("OAuthCompletePage", () => {
    const originalLocation = window.location;
    const replace = vi.fn();
    const close = vi.fn();

    function setSearch(search: string) {
        Object.defineProperty(window, "location", {
            configurable: true,
            value: { ...originalLocation, origin: originalLocation.origin, search, replace },
        });
    }

    beforeEach(() => {
        vi.clearAllMocks();
        window.close = close;
    });

    afterEach(() => {
        Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
        Object.defineProperty(window, "opener", { configurable: true, value: null });
    });

    it("posts the outcome to the opener, restricted to this origin, and closes", () => {
        const postMessage = vi.fn();
        Object.defineProperty(window, "opener", { configurable: true, value: { closed: false, postMessage } });
        setSearch("?status=success&server_id=srv-1");

        render(<OAuthCompletePage />);

        expect(postMessage).toHaveBeenCalledWith(
            { type: "mcp-hub-oauth", status: "success", server_id: "srv-1", error: null },
            originalLocation.origin
        );
        expect(close).toHaveBeenCalled();
        expect(replace).not.toHaveBeenCalled();
    });

    it("redirects to the server when there is no opener", () => {
        Object.defineProperty(window, "opener", { configurable: true, value: null });
        setSearch("?status=success&server_id=srv-1");

        render(<OAuthCompletePage />);

        expect(replace).toHaveBeenCalledWith("/servers/srv-1");
        expect(close).not.toHaveBeenCalled();
    });

    it("redirects to the servers list with the error when there is no opener", () => {
        Object.defineProperty(window, "opener", { configurable: true, value: null });
        setSearch("?status=error&error=state_expired");

        render(<OAuthCompletePage />);

        expect(replace).toHaveBeenCalledWith("/servers?oauth_error=state_expired");
    });
});
