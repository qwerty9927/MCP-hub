import type { NextConfig } from "next";
import path from "path";

// Next.js loads frontend/.env* before this file, so a missing setting stops `next build` / `next dev` here.
const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
if (!apiBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set: add it to frontend/.env (see frontend/.env.example)");
}
// The backend origin the console's server forwards API calls to (src/lib/config.ts API_PROXY_PATH). It can differ from
// the public one: inside Docker Compose it is the `backend` service.
const apiProxyTarget = process.env.API_PROXY_TARGET?.replace(/\/$/, "");
if (!apiProxyTarget) {
    throw new Error("API_PROXY_TARGET is not set: add it to frontend/.env (see frontend/.env.example)");
}
// Same path on both sides, so the refresh token cookie's Path (/api/v1/auth/...) matches on the console's origin.
const apiPath = new URL(apiBaseUrl).pathname.replace(/\/$/, "");

const nextConfig: NextConfig = {
    // The Docker image sets NEXT_OUTPUT=standalone to ship a self-contained server (.next/standalone);
    // local `pnpm build` / `pnpm start` keep the default output.
    output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
    reactStrictMode: true,
    poweredByHeader: false,
    // Browser -> console origin -> backend: the refresh token cookie stays first-party (Vercel and the API are different sites).
    async rewrites() {
        return [{ source: `${apiPath}/:path*`, destination: `${apiProxyTarget}${apiPath}/:path*` }];
    },
    webpack: (config) => {
        config.resolve.alias = {
            ...config.resolve.alias,
            "@": path.resolve(__dirname, "src"),
        };
        return config;
    },
};

export default nextConfig;
