"""
Root conftest.py — shared fixtures for all test suites.

Environment variables are set here so they're available before any module-level
imports in the app trigger DATABASE_URL / REDIS_URL lookups.
"""

from __future__ import annotations

import os

import pytest

# ── Minimal environment for unit tests (no real services required) ────────────
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_VERSION", "0.0.0-test")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("ALGORAND_ALGOD_ADDRESS", "http://localhost:4001")
os.environ.setdefault(
    "ALGORAND_ALGOD_TOKEN",
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
)
os.environ.setdefault("ESCROW_DRY_RUN_ENABLED", "true")
os.environ.setdefault("X402_SIMULATION_MODE", "false")
os.environ.setdefault("WEBHOOK_DELIVERY_URL", "")
os.environ.setdefault("WEBHOOK_SIGNING_SECRET", "test-webhook-secret")
os.environ.setdefault("WEBHOOK_TIMEOUT_SECONDS", "3")
os.environ.setdefault("WEBHOOK_MAX_RETRIES", "1")
os.environ.setdefault("X402_PAYMENT_SECRET", "test-payment-secret")
os.environ.setdefault("LLM_PROVIDER", "stub")


# anyio backend for async tests (pytest-anyio / anyio)
@pytest.fixture(params=["asyncio"])
def anyio_backend(request: pytest.FixtureRequest) -> str:
    return str(request.param)
