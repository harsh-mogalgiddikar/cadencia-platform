"""
Integration tests for GET /health endpoint.

Tests use FastAPI's AsyncClient with the three health check functions
patched — no real DB, Redis, or Algorand required.

Tests:
    test_health_returns_200
    test_health_all_checks_ok
    test_health_response_structure_valid
    test_health_includes_request_id_header
    test_health_degraded_when_algorand_fails
    test_health_unhealthy_when_db_fails
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.health.router import CheckResult, _compute_overall_status


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _ok() -> CheckResult:
    return CheckResult(status="ok", latency_ms=1.0)


def _err(detail: str = "error") -> CheckResult:
    return CheckResult(status="error", latency_ms=99.0, detail=detail)


def _make_app_with_all_ok() -> object:
    """Create app with all health checks and startup checks mocked to pass."""
    from main import create_app

    with (
        patch("src.health.router._check_db", new_callable=AsyncMock, return_value=_ok()),
        patch("src.health.router._check_redis", new_callable=AsyncMock, return_value=_ok()),
        patch("src.health.router._check_algorand", new_callable=AsyncMock, return_value=_ok()),
    ):
        # Patch the lifespan startup checks
        with (
            patch("main.get_engine", return_value=MagicMock()),
            patch("main.redis_module.ping", new_callable=AsyncMock, return_value=True),
            patch("httpx.AsyncClient"),
        ):
            return create_app()


# ── Tests using _compute_overall_status (pure logic — no HTTP) ────────────────

def test_health_degraded_when_algorand_fails() -> None:
    """Only Algorand down → 'degraded'."""
    assert _compute_overall_status(_ok(), _ok(), _err("conn refused"), _ok(), _ok()) == "degraded"


def test_health_unhealthy_when_db_fails() -> None:
    """DB down → 'unhealthy'."""
    assert _compute_overall_status(_err("db down"), _ok(), _ok(), _ok(), _ok()) == "unhealthy"


def test_health_unhealthy_when_redis_fails() -> None:
    """Redis down → 'unhealthy'."""
    assert _compute_overall_status(_ok(), _err("PING failed"), _ok(), _ok(), _ok()) == "unhealthy"


def test_health_unhealthy_when_all_fail() -> None:
    assert _compute_overall_status(_err(), _err(), _err(), _err(), _err()) == "unhealthy"


def test_health_healthy_when_all_ok() -> None:
    assert _compute_overall_status(_ok(), _ok(), _ok(), _ok(), _ok()) == "healthy"


# ── HTTP-level tests (mocked infrastructure) ──────────────────────────────────

@pytest.mark.anyio
async def test_health_returns_200() -> None:
    """GET /health must always return HTTP 200."""
    from main import create_app

    async def mock_startup(app: object) -> object:
        yield

    ok = _ok()
    with (
        patch("src.health.router._check_db", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_redis", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_algorand", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_llm_api", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_circuits", new_callable=AsyncMock, return_value=ok),
        patch("main.get_engine", return_value=MagicMock()),
        patch("main.redis_module.ping", new_callable=AsyncMock, return_value=True),
        patch("httpx.AsyncClient"),
    ):
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.get("/health")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_health_all_checks_ok() -> None:
    from main import create_app

    ok = _ok()
    with (
        patch("src.health.router._check_db", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_redis", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_algorand", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_llm_api", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_circuits", new_callable=AsyncMock, return_value=ok),
        patch("main.get_engine", return_value=MagicMock()),
        patch("main.redis_module.ping", new_callable=AsyncMock, return_value=True),
        patch("httpx.AsyncClient"),
    ):
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.get("/health")

    body = response.json()
    assert body["status"] == "healthy"
    assert body["checks"]["db"]["status"] == "ok"
    assert body["checks"]["redis"]["status"] == "ok"
    assert body["checks"]["algorand"]["status"] == "ok"


@pytest.mark.anyio
async def test_health_response_structure_valid() -> None:
    from main import create_app

    ok = _ok()
    with (
        patch("src.health.router._check_db", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_redis", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_algorand", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_llm_api", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_circuits", new_callable=AsyncMock, return_value=ok),
        patch("main.get_engine", return_value=MagicMock()),
        patch("main.redis_module.ping", new_callable=AsyncMock, return_value=True),
        patch("httpx.AsyncClient"),
    ):
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.get("/health")

    body = response.json()
    # Required top-level fields
    assert "status" in body
    assert "checks" in body
    assert "version" in body
    assert "environment" in body
    # Each check has status and latency_ms
    for check_name in ("db", "redis", "algorand"):
        assert check_name in body["checks"]
        check = body["checks"][check_name]
        assert "status" in check
        assert "latency_ms" in check


@pytest.mark.anyio
async def test_health_includes_request_id_header() -> None:
    from main import create_app

    ok = _ok()
    with (
        patch("src.health.router._check_db", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_redis", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_algorand", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_llm_api", new_callable=AsyncMock, return_value=ok),
        patch("src.health.router._check_circuits", new_callable=AsyncMock, return_value=ok),
        patch("main.get_engine", return_value=MagicMock()),
        patch("main.redis_module.ping", new_callable=AsyncMock, return_value=True),
        patch("httpx.AsyncClient"),
    ):
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.get("/health")

    assert "x-request-id" in response.headers


@pytest.mark.anyio
async def test_health_always_returns_200_when_all_fail() -> None:
    """
    /health must return HTTP 200 even when all checks fail.
    context.md §16: monitoring systems parse body, not status code.
    """
    from main import create_app

    err = _err("service down")
    with (
        patch("src.health.router._check_db", new_callable=AsyncMock, return_value=err),
        patch("src.health.router._check_redis", new_callable=AsyncMock, return_value=err),
        patch("src.health.router._check_algorand", new_callable=AsyncMock, return_value=err),
        patch("src.health.router._check_llm_api", new_callable=AsyncMock, return_value=err),
        patch("src.health.router._check_circuits", new_callable=AsyncMock, return_value=err),
        patch("main.get_engine", return_value=MagicMock()),
        patch("main.redis_module.ping", new_callable=AsyncMock, return_value=False),
        patch("httpx.AsyncClient"),
    ):
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unhealthy"
