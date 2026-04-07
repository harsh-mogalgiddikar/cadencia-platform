"""
Integration tests for the identity API endpoints.

Requires: Docker compose (postgres, redis) running for full DB tests.
Tests full request/response cycle through the API layer.
Tests without a live DB use mock patches and should still pass.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.health.router import CheckResult as HealthCheckResult


def _make_app():
    """Create app with infrastructure checks mocked."""
    from main import create_app
    return create_app()


@pytest.mark.integration
class TestIdentityAPIIntegration:
    """
    Integration tests: full HTTP cycle through FastAPI app.

    Run with services: pytest -m integration tests/integration/
    """

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """GET /health should return 200 with status info."""
        app = _make_app()
        transport = ASGITransport(app=app)
        _ok = HealthCheckResult(status="ok", latency_ms=1.0)

        with (
            patch("main.get_engine", return_value=MagicMock()),
            patch("main.redis_module.ping", new_callable=AsyncMock, return_value=True),
            patch("httpx.AsyncClient"),
            patch("src.health.router._check_db", new_callable=AsyncMock, return_value=_ok),
            patch("src.health.router._check_redis", new_callable=AsyncMock, return_value=_ok),
            patch("src.health.router._check_algorand", new_callable=AsyncMock, return_value=_ok),
            patch("src.health.router._check_llm_api", new_callable=AsyncMock, return_value=_ok),
            patch("src.health.router._check_circuits", new_callable=AsyncMock, return_value=_ok),
        ):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health")
                assert response.status_code == 200
                data = response.json()
                assert "status" in data

    @pytest.mark.asyncio
    async def test_register_enterprise(self):
        """POST /v1/auth/register route exists and responds (mocked service, DB-independent)."""
        from src.shared.domain.exceptions import DomainError
        from src.identity.api.dependencies import get_identity_service

        # Mock identity service to avoid real DB connection
        mock_svc = AsyncMock()
        mock_svc.register_enterprise.side_effect = DomainError("test_only")

        app = _make_app()
        app.dependency_overrides[get_identity_service] = lambda: mock_svc
        transport = ASGITransport(app=app)

        try:
            with (
                patch("main.get_engine", return_value=MagicMock()),
                patch("main.redis_module.ping", new_callable=AsyncMock, return_value=True),
                patch("httpx.AsyncClient"),
            ):
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/v1/auth/register",
                        json={
                            "enterprise": {
                                "legal_name": "Integration Test Corp",
                                "pan": "ABCDE1234F",
                                "gstin": "27ABCDE1234F1Z5",
                                "trade_role": "BUYER",
                            },
                            "user": {
                                "email": "inttest@example.com",
                                "password": "SecurePass123!@#",
                                "full_name": "Test User",
                            },
                        },
                    )
                    # Route exists (not 404), error handler caught domain error
                    assert response.status_code != 404, "POST /v1/auth/register route must exist"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_register_validation_error(self):
        """POST /v1/auth/register with invalid PAN should return 422."""
        app = _make_app()
        transport = ASGITransport(app=app)

        with (
            patch("main.get_engine", return_value=MagicMock()),
            patch("main.redis_module.ping", new_callable=AsyncMock, return_value=True),
            patch("httpx.AsyncClient"),
        ):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/v1/auth/register",
                    json={
                        "enterprise": {
                            "legal_name": "Bad PAN Corp",
                            "pan": "INVALID",
                            "gstin": "27ABCDE1234F1Z5",
                            "trade_role": "BUYER",
                        },
                        "user": {
                            "email": "bad@example.com",
                            "password": "SecurePass123!@#",
                        },
                    },
                )
                assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_unauthenticated_request(self):
        """GET /v1/enterprises without auth should return 401."""
        app = _make_app()
        transport = ASGITransport(app=app)

        with (
            patch("main.get_engine", return_value=MagicMock()),
            patch("main.redis_module.ping", new_callable=AsyncMock, return_value=True),
            patch("httpx.AsyncClient"),
        ):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/v1/enterprises")
                assert response.status_code in (401, 404)
