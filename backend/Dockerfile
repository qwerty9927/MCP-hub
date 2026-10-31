# Multi-stage Docker build for MCP Hub Backend
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency definition
COPY pyproject.toml .

# Install dependencies into virtual environment
RUN uv venv /app/.venv && \
    uv pip install -p /app/.venv -r pyproject.toml

# Final runtime image
FROM python:3.12-slim AS runner

WORKDIR /app

# Create unprivileged application user
RUN groupadd -g 1000 mcphub && \
    useradd -u 1000 -g mcphub -s /bin/bash -m mcphub

# Copy virtual environment and code
COPY --from=builder /app/.venv /app/.venv
COPY . /app

# Set environment paths and permissions
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1

RUN chown -R mcphub:mcphub /app

USER mcphub

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
