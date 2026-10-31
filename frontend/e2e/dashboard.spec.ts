import { test, expect } from "@playwright/test";

test.describe("MCP Hub Navigation and Dashboard Flow", () => {
    test("navigates to overview page and verifies headers", async ({ page }) => {
        await page.goto("/overview");
        await expect(page).toHaveTitle(/MCP Hub/);
        await expect(page.getByRole("heading", { name: /Hub Overview/i })).toBeVisible();
    });

    test("navigates to servers list page", async ({ page }) => {
        await page.goto("/servers");
        await expect(page.getByRole("heading", { name: /MCP Servers/i })).toBeVisible();
        await expect(page.getByRole("link", { name: /Register Server/i })).toBeVisible();
    });

    test("navigates to tool catalog", async ({ page }) => {
        await page.goto("/tools");
        await expect(page.getByRole("heading", { name: /Unified Tool Catalog/i })).toBeVisible();
    });

    test("navigates to tool playground", async ({ page }) => {
        await page.goto("/playground");
        await expect(page.getByRole("heading", { name: /Tool Playground/i })).toBeVisible();
    });

    test("navigates to execution history", async ({ page }) => {
        await page.goto("/executions");
        await expect(page.getByRole("heading", { name: /Execution History/i })).toBeVisible();
    });

    test("navigates to settings and checks diagnostics", async ({ page }) => {
        await page.goto("/settings");
        await expect(page.getByRole("heading", { name: /Settings & Telemetry/i })).toBeVisible();
        await expect(page.getByText(/Backend Connection/i)).toBeVisible();
    });
});
