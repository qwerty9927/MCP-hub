import type { NextConfig } from "next";
import path from "path";

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
