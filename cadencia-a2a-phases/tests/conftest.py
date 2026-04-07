"""
Shared pytest fixtures for Cadencia tests.

Provides:
- async_client: HTTPX async test client with the FastAPI app
- db_session: SQLAlchemy async session (auto-rollback per test)
- redis_mock: FakeRedis for cache testing
- factory fixtures: authenticated client, sample enterprises, etc.
"""

from __future__ import annotations

import os
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio

# Ensure test env vars are set before any app imports
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-change-me")
os.environ.setdefault("X402_SIMULATION_MODE", "true")
os.environ.setdefault(
    "ALGORAND_ESCROW_CREATOR_MNEMONIC",
    "abandon abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon abandon abandon "
    "abandon abandon about",
)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# ── Sample Entity IDs ─────────────────────────────────────────────────────────

SAMPLE_ENTERPRISE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SAMPLE_USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
SAMPLE_SESSION_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


# ── Marker auto-use ───────────────────────────────────────────────────────────

def pytest_collection_modifyitems(config, items):
    """Auto-apply markers based on test path."""
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
