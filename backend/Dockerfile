# ═══════════════════════════════════════════════════
# Legis Agent — Production Dockerfile
# ═══════════════════════════════════════════════════
# Multi-stage build:
#   Stage 1 (builder) — installs all Python deps with build-essential
#   Stage 2 (runtime) — slim image with only runtime deps + app code
# ═══════════════════════════════════════════════════


# ── Stage 1: Build dependencies ─────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies needed for native Python extensions
# (numpy, psycopg2-binary, etc. may need compilation on some platforms)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install project dependencies (with optional extras for pgvector/pinecone)
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[all]"


# ── Stage 2: Runtime ────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install only the runtime system deps needed (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder (no build-essential required)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY app/ app/
COPY prompts/ prompts/

# Port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run — use uvicorn directly (avoid python -m overhead)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
