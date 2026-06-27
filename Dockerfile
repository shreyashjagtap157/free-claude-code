# syntax=docker/dockerfile:1
# Multi-stage build for free-claude-code proxy

# ── Base stage ──────────────────────────────────────────────────────
FROM python:3.14-slim AS base

WORKDIR /app

ENV \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PACKAGES=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ── Build stage ─────────────────────────────────────────────────────
FROM base AS builder

COPY pyproject.toml ./
COPY .env.example ./

# Install runtime dependencies
RUN uv sync --no-dev --no-install-project

# ── Runtime stage ───────────────────────────────────────────────────
FROM base AS runtime

# Create non-root user
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

COPY --from=builder /app /app
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

# Copy application code
COPY api/ api/
COPY cli/ cli/
COPY config/ config/
COPY core/ core/
COPY messaging/ messaging/
COPY providers/ providers/

# Ensure .env.example is available as package resource
RUN mkdir -p /app/cli && cp /app/.env.example /app/cli/env.example 2>/dev/null || true

# Create data directory with proper permissions
RUN mkdir -p /data && chown -R app:app /data

USER app

EXPOSE 8080

# Default: start the proxy server
CMD ["uv", "run", "fcc-server"]
