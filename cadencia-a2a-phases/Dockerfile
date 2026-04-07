# ═══════════════════════════════════════════════════════════════
# Cadencia — Multi-Stage Dockerfile
# context.md §10: ap-south-1 — image built for linux/amd64
# Targets: base → builder → production → migration → test
# ═══════════════════════════════════════════════════════════════

# ── BASE stage ────────────────────────────────────────────────
FROM python:3.12-slim AS base

# Security: non-root user
RUN groupadd --gid 1001 cadencia \
    && useradd --uid 1001 --gid 1001 --no-create-home cadencia

WORKDIR /app

# Runtime OS deps only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip + setuptools (setuptools>=68 required for setuptools.backends on Python 3.12)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# ── BUILDER stage ─────────────────────────────────────────────
FROM base AS builder

# Install Python deps into /install prefix (isolate from system)
COPY pyproject.toml ./
# Ensure latest setuptools before installing project (fixes setuptools.backends on py3.12)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --prefix=/install .

# ── PRODUCTION stage ──────────────────────────────────────────
FROM base AS production

LABEL maintainer="cadencia-team" \
      description="Cadencia API — AI-native B2B trade marketplace" \
      version="0.1.0"

# Copy installed deps from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=cadencia:cadencia src/ ./src/
COPY --chown=cadencia:cadencia main.py ./
COPY --chown=cadencia:cadencia alembic/ ./alembic/
COPY --chown=cadencia:cadencia alembic.ini ./
COPY --chown=cadencia:cadencia conftest.py ./
COPY --chown=cadencia:cadencia pyproject.toml ./

# Drop to non-root
USER cadencia

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Production entrypoint: uvicorn with uvloop
CMD ["python", "-m", "uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "warning", \
     "--timeout-graceful-shutdown", "30"]

# ── MIGRATION stage ───────────────────────────────────────────
FROM production AS migration
# Run as one-off ECS task before main deployment
USER cadencia
CMD ["python", "-m", "alembic", "upgrade", "head"]

# ── TEST stage ────────────────────────────────────────────────
FROM base AS test

COPY --from=builder /install /usr/local

# Install dev/test deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]" 2>/dev/null || true
RUN pip install --no-cache-dir pytest pytest-anyio pytest-asyncio

# Copy the full project
COPY --chown=cadencia:cadencia . .

USER cadencia
CMD ["python", "-m", "pytest", "tests/unit/", "-x", "--tb=short", "-q"]
