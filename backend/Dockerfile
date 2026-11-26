# Multi-stage Docker build for MCP Hub Backend
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv package manager (pinned for reproducible builds)
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /uvx /bin/

# Copy dependency definition (uv.lock is not committed, so dependencies resolve from pyproject.toml)
COPY pyproject.toml .

# Install dependencies into virtual environment
RUN uv venv /app/.venv && \
    uv pip install --no-cache -p /app/.venv -r pyproject.toml

# Node.js and npm, copied into the runtime image for stdio MCP servers started with `node` / `npx`
FROM node:22-bookworm-slim AS node

# Final runtime image
FROM python:3.12-slim AS runner

WORKDIR /app

# Create unprivileged application user
RUN groupadd -g 1000 mcphub && \
    useradd -u 1000 -g mcphub -s /bin/bash -m mcphub

# Runtimes for stdio MCP servers, which the backend starts as subprocesses:
# python (the app's own venv), uv / uvx, and node / npm / npx.
COPY --from=builder /bin/uv /bin/uvx /usr/local/bin/
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# Copy the virtual environment
COPY --from=builder --chown=mcphub:mcphub /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN chown mcphub:mcphub /app
USER mcphub

# Pre-download the tool-search embedding model so EMBEDDING_PROVIDER=local containers do not fetch it on first start.
# Pass the local_id of the EMBEDDING_MODELS entry EMBEDDING_MODEL names (ADR-0010); the cache dir matches EMBEDDING_CACHE_DIR.
ARG EMBEDDING_LOCAL_MODEL_ID=BAAI/bge-small-en-v1.5
RUN python -c "import sys; from fastembed import TextEmbedding; TextEmbedding(sys.argv[1], cache_dir='/app/.cache/fastembed')" "$EMBEDDING_LOCAL_MODEL_ID"

# Copy application code last so code changes do not invalidate the layers above (see .dockerignore)
COPY --chown=mcphub:mcphub . /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" || exit 1

# Apply database migrations, then start the API
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
