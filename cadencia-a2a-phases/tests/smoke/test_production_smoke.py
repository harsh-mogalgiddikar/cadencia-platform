# Production Smoke Tests — run post-deploy against live URL.
# Uses httpx for HTTP calls. No database fixtures needed.
# All smoke test data isolated by SMOKE_TEST=true header.
#
# Run: pytest tests/smoke/ --base-url=https://api.cadencia.in -v
# Skipped automatically when no server is reachable at SMOKE_TEST_BASE_URL.

from __future__ import annotations

import os

import httpx
import pytest

BASE_URL = os.environ.get("SMOKE_TEST_BASE_URL", "http://localhost:8000")


def _server_reachable() -> bool:
    try:
        httpx.get(f"{BASE_URL}/health", timeout=2.0)
        return True
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


pytestmark = pytest.mark.skipif(
    not _server_reachable(),
    reason=f"Smoke tests require a live server at {BASE_URL}. Set SMOKE_TEST_BASE_URL.",
)


@pytest.fixture
def client():
    """Shared httpx client for smoke tests."""
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
        yield c


class TestHealthCheck:
    """Verify /health returns 200 with all checks."""

    def test_health_returns_200(self, client: httpx.Client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_all_checks(self, client: httpx.Client):
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")
        assert "db" in data["checks"]
        assert "redis" in data["checks"]
        assert "algorand" in data["checks"]

    def test_health_has_version(self, client: httpx.Client):
        resp = client.get("/health")
        data = resp.json()
        assert "version" in data
        assert "environment" in data


class TestSecurityHeaders:
    """Verify security headers are present on responses."""

    def test_security_headers_present(self, client: httpx.Client):
        resp = client.get("/health")
        headers = resp.headers
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"
        assert "x-request-id" in headers

    def test_timing_header_present(self, client: httpx.Client):
        resp = client.get("/health")
        assert "x-response-time-ms" in resp.headers


class TestAPIRoutes:
    """Verify API routes respond (even if unauthenticated → 401/403)."""

    def test_auth_login_route_exists(self, client: httpx.Client):
        resp = client.post(
            "/v1/auth/login",
            json={"email": "smoke@test.invalid", "password": "NotReal123"},
        )
        # Should return 401 (wrong creds) not 404 (route missing)
        assert resp.status_code in (401, 422, 400)

    def test_marketplace_rfq_requires_auth(self, client: httpx.Client):
        resp = client.post(
            "/v1/marketplace/rfq",
            json={"raw_text": "Need 500MT HR Coil for Mumbai delivery"},
        )
        assert resp.status_code in (401, 403)

    def test_sessions_requires_auth(self, client: httpx.Client):
        resp = client.get("/v1/sessions/00000000-0000-0000-0000-000000000000")
        assert resp.status_code in (401, 403)

    def test_openapi_json_available_in_dev(self, client: httpx.Client):
        resp = client.get("/openapi.json")
        # In dev: 200. In production: 404/disabled
        assert resp.status_code in (200, 404)


class TestRequestLimits:
    """Verify request body size limits."""

    def test_large_body_rejected(self, client: httpx.Client):
        # 2MB body — should be rejected by 1MB limit
        large_body = "x" * (2 * 1024 * 1024)
        resp = client.post(
            "/v1/marketplace/rfq",
            json={"raw_text": large_body},
            headers={"Content-Length": str(len(large_body))},
        )
        # Should be 413 (payload too large) or 401 (auth check first)
        assert resp.status_code in (413, 401, 403, 422)


class TestResponseFormat:
    """Verify API response envelope format."""

    def test_error_response_format(self, client: httpx.Client):
        resp = client.get("/v1/enterprises/00000000-0000-0000-0000-000000000000")
        # Should be 401 with proper error format
        assert resp.status_code in (401, 403)
        data = resp.json()
        assert "status" in data or "detail" in data
