import type { NextConfig } from "next";
import path from "path";

// Next.js loads frontend/.env* before this file, so a missing API URL stops `next build` / `next dev` here.
if (!process.env.NEXT_PUBLIC_API_BASE_URL) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set: add it to frontend/.env (see frontend/.env.example)");
}

const nextConfig: NextConfig = {
    // The Docker image sets NEXT_OUTPUT=standalone to ship a self-contained server (.next/standalone);
    // local `pnpm build` / `pnpm start` keep the default output.
    output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
    reactStrictMode: true,
    poweredByHeader: false,
    webpack: (config) => {
        config.resolve.alias = {
            ...config.resolve.alias,
            "@": path.resolve(__dirname, "src"),
        };
        return config;
    },
};

export default nextConfig;
