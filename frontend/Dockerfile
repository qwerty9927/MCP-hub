# Multi-stage production Dockerfile for MCP Hub Next.js Frontend
FROM node:22-alpine AS base
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10.23.0 --activate

# Step 1: Install dependencies
FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Step 2: Build application
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
# Emit a self-contained server in .next/standalone (see next.config.ts)
ENV NEXT_OUTPUT=standalone
# NEXT_PUBLIC_* values are inlined into the browser bundle at build time. `next build` reads them from the
# .env.local / .env files in the build context; the optional build argument overrides those when passed.
# The API URL is the address the user's browser uses to reach the backend, not a container-internal one.
ARG NEXT_PUBLIC_API_BASE_URL
# The backend origin the console's server proxies /api/v1 to (next.config.ts rewrites, baked in at build time).
# Unlike the API URL, this one is reached from the server, so in Compose it is the `backend` service.
ARG API_PROXY_TARGET
RUN if [ -z "$NEXT_PUBLIC_API_BASE_URL" ]; then unset NEXT_PUBLIC_API_BASE_URL; fi && \
    if [ -z "$API_PROXY_TARGET" ]; then unset API_PROXY_TARGET; fi && \
    pnpm build

# Step 3: Production runner (only the standalone server, static assets and public files)
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:' + (process.env.PORT || 3000) + '/login').then((r) => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "server.js"]
