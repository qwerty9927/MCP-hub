import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "url";
import path from "path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
    plugins: [react()],
    test: {
        environment: "jsdom",
        globals: true,
        setupFiles: ["./src/test/setup.ts"],
        // Tests do not load frontend/.env; src/lib/config.ts requires the API URL.
        env: { NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000/api/v1" },
        include: ["src/**/*.{test,spec}.{ts,tsx}"],
    },
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
});
