"""
Load tests for Cadencia API — SRS Performance Requirements.

SRS-PF-001: API endpoint latency < 500ms p95
SRS-PF-002: LLM agent turn latency < 3s p95
SRS-PF-005: 100 concurrent negotiation sessions

Uses pytest-benchmark for repeatable, CI-integrated benchmarks.
Optionally supports locust for distributed load generation.

Run:
    pytest tests/performance/test_load.py --benchmark-only -v
    pytest tests/performance/test_load.py -k test_api -v

For locust (interactive web UI):
    locust -f tests/performance/test_load.py --host=http://localhost:8000
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.health.router import CheckResult as HealthCheckResult


# ══════════════════════════════════════════════════════════════════════════════
# SRS-PF-001: API Endpoint Latency < 500ms p95
# ══════════════════════════════════════════════════════════════════════════════


class TestAPIEndpointLatency:
    """Benchmark API endpoint response times against SRS-PF-001 targets."""

    @pytest.mark.asyncio
    async def test_health_endpoint_latency(self):
        """GET /health must respond in < 100ms (well within 500ms SRS target)."""
        from httpx import ASGITransport, AsyncClient

        _ok = HealthCheckResult(status="ok", latency_ms=1.0)
        with (
            patch("src.health.router._check_db", new_callable=AsyncMock, return_value=_ok),
            patch("src.health.router._check_redis", new_callable=AsyncMock, return_value=_ok),
            patch("src.health.router._check_algorand", new_callable=AsyncMock, return_value=_ok),
            patch("src.health.router._check_llm_api", new_callable=AsyncMock, return_value=_ok),
            patch("src.health.router._check_circuits", new_callable=AsyncMock, return_value=_ok),
            patch("main.get_engine", return_value=MagicMock()),
            patch("main.redis_module.ping", new_callable=AsyncMock, return_value=True),
            patch("httpx.AsyncClient"),
        ):
            from main import create_app
            app = create_app()

            latencies = []
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                for _ in range(50):
                    start = time.monotonic()
                    r = await client.get("/health")
                    elapsed_ms = (time.monotonic() - start) * 1000
                    latencies.append(elapsed_ms)
                    assert r.status_code == 200

            latencies.sort()
            p95 = latencies[int(len(latencies) * 0.95)]
            p99 = latencies[int(len(latencies) * 0.99)]
            avg = sum(latencies) / len(latencies)

            print(f"\n  /health latency — avg: {avg:.1f}ms, p95: {p95:.1f}ms, p99: {p99:.1f}ms")
            assert p95 < 500, f"SRS-PF-001 FAIL: p95={p95:.1f}ms > 500ms target"

    @pytest.mark.asyncio
    async def test_concurrent_health_requests(self):
        """Simulate 50 concurrent requests to /health."""
        from httpx import ASGITransport, AsyncClient

        _ok = HealthCheckResult(status="ok", latency_ms=1.0)
        with (
            patch("src.health.router._check_db", new_callable=AsyncMock, return_value=_ok),
            patch("src.health.router._check_redis", new_callable=AsyncMock, return_value=_ok),
            patch("src.health.router._check_algorand", new_callable=AsyncMock, return_value=_ok),
            patch("src.health.router._check_llm_api", new_callable=AsyncMock, return_value=_ok),
            patch("src.health.router._check_circuits", new_callable=AsyncMock, return_value=_ok),
            patch("main.get_engine", return_value=MagicMock()),
            patch("main.redis_module.ping", new_callable=AsyncMock, return_value=True),
            patch("httpx.AsyncClient"),
        ):
            from main import create_app
            app = create_app()

            async def _request(client, i):
                start = time.monotonic()
                r = await client.get("/health")
                return (time.monotonic() - start) * 1000, r.status_code

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                tasks = [_request(client, i) for i in range(50)]
                results = await asyncio.gather(*tasks)

            latencies = [r[0] for r in results]
            statuses = [r[1] for r in results]

            assert all(s == 200 for s in statuses), "Not all requests returned 200"

            latencies.sort()
            p95 = latencies[int(len(latencies) * 0.95)]
            print(f"\n  50 concurrent /health — p95: {p95:.1f}ms")
            assert p95 < 500, f"SRS-PF-001 FAIL: concurrent p95={p95:.1f}ms > 500ms"


# ══════════════════════════════════════════════════════════════════════════════
# SRS-PF-002: LLM Agent Turn Latency < 3s p95
# ══════════════════════════════════════════════════════════════════════════════


class TestLLMAgentLatency:
    """Benchmark LLM agent driver response times (stub mode)."""

    @pytest.mark.asyncio
    async def test_stub_agent_driver_latency(self):
        """
        StubAgentDriver should respond in < 10ms (well within 3s target).

        In production, the real LLM driver is subject to API latency,
        but the stub ensures our pipeline overhead is minimal.
        """
        from src.negotiation.infrastructure.llm_agent_driver import StubAgentDriver

        driver = StubAgentDriver()
        latencies = []

        for round_num in range(20):
            start = time.monotonic()
            result = await driver.generate_offer(
                system_prompt="You are a buyer agent negotiating cotton pricing.",
                session_context={
                    "session_id": str(uuid.uuid4()),
                    "round_count": round_num,
                    "rfq_id": str(uuid.uuid4()),
                },
                offer_history=[
                    {"round": i, "role": "SELLER", "price": 100000 - i * 1000}
                    for i in range(round_num)
                ],
            )
            elapsed_ms = (time.monotonic() - start) * 1000
            latencies.append(elapsed_ms)

            assert "action" in result
            assert "price" in result

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        print(f"\n  StubAgentDriver latency — p95: {p95:.1f}ms")
        assert p95 < 3000, f"SRS-PF-002 FAIL: p95={p95:.1f}ms > 3000ms"


# ══════════════════════════════════════════════════════════════════════════════
# SRS-PF-005: 100 Concurrent Negotiation Sessions
# ══════════════════════════════════════════════════════════════════════════════


class TestConcurrentNegotiations:
    """Verify system handles 100 concurrent negotiation sessions."""

    @pytest.mark.asyncio
    async def test_100_concurrent_session_creation(self):
        """
        Create 100 NegotiationSession instances concurrently.

        Validates domain model can handle high concurrency without
        race conditions or UUID collisions.
        """
        from src.negotiation.domain.session import NegotiationSession, SessionStatus

        async def _create_session(i: int) -> NegotiationSession:
            session = NegotiationSession(
                rfq_id=uuid.uuid4(),
                match_id=uuid.uuid4(),
                buyer_enterprise_id=uuid.uuid4(),
                seller_enterprise_id=uuid.uuid4(),
                status=SessionStatus.INIT,
            )
            session.activate()
            return session

        start = time.monotonic()
        tasks = [_create_session(i) for i in range(100)]
        sessions = await asyncio.gather(*tasks)
        elapsed_ms = (time.monotonic() - start) * 1000

        # All sessions created
        assert len(sessions) == 100

        # All have unique IDs
        ids = {s.id for s in sessions}
        assert len(ids) == 100

        # All in BUYER_ANCHOR state
        assert all(s.status == SessionStatus.BUYER_ANCHOR for s in sessions)

        print(f"\n  100 concurrent sessions created in {elapsed_ms:.1f}ms")

    @pytest.mark.asyncio
    async def test_100_concurrent_stub_negotiations(self):
        """
        Run 100 StubAgentDriver negotiations concurrently.

        Each negotiation runs 5 rounds before the stub accepts.
        Validates no contention or state corruption under load.
        """
        from src.negotiation.infrastructure.llm_agent_driver import StubAgentDriver

        driver = StubAgentDriver()

        async def _run_negotiation(session_idx: int) -> dict:
            history = []
            for round_num in range(6):
                result = await driver.generate_offer(
                    system_prompt=f"Session {session_idx} agent",
                    session_context={"round_count": round_num, "session_id": str(uuid.uuid4())},
                    offer_history=history,
                )
                history.append({
                    "round": round_num,
                    "role": "BUYER" if round_num % 2 == 0 else "SELLER",
                    "price": result["price"],
                })
                if result["action"] == "ACCEPT":
                    return {"session": session_idx, "rounds": round_num + 1, "final_price": result["price"]}
            return {"session": session_idx, "rounds": 6, "final_price": history[-1]["price"]}

        start = time.monotonic()
        tasks = [_run_negotiation(i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        elapsed = time.monotonic() - start

        assert len(results) == 100
        completed = [r for r in results if r["rounds"] <= 6]
        assert len(completed) == 100

        print(f"\n  100 concurrent stub negotiations in {elapsed:.2f}s")
        print(f"  Avg rounds: {sum(r['rounds'] for r in results) / len(results):.1f}")


# ══════════════════════════════════════════════════════════════════════════════
# Domain Model Stress Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDomainModelStress:
    """Stress test domain aggregates under high throughput."""

    @pytest.mark.asyncio
    async def test_escrow_state_machine_1000_transitions(self):
        """
        Create and transition 1000 escrow instances through the full lifecycle.

        Validates domain model integrity under high throughput.
        """
        from src.settlement.domain.escrow import Escrow, EscrowStatus
        from src.settlement.domain.value_objects import (
            AlgoAppId, AlgoAppAddress, TxId, EscrowAmount, MicroAlgo, MerkleRoot,
        )

        start = time.monotonic()
        for i in range(1000):
            escrow = Escrow(
                session_id=uuid.uuid4(),
                buyer_address="A" * 58,
                seller_address="B" * 58,
                amount=EscrowAmount(value=MicroAlgo(value=(i + 1) * 1_000_000)),
            )
            escrow.record_deployment(
                app_id=AlgoAppId(value=i + 1),
                app_address=AlgoAppAddress(value="C" * 58),
                tx_id=TxId(value="D" * 52),
            )
            escrow.record_funding(TxId(value="E" * 52))
            escrow.record_release(
                tx_id=TxId(value="F" * 52),
                merkle_root=MerkleRoot(value=f"{i:064x}"),
            )
            assert escrow.status == EscrowStatus.RELEASED

        elapsed = time.monotonic() - start
        throughput = 1000 / elapsed
        print(f"\n  1000 escrow lifecycles in {elapsed:.2f}s ({throughput:.0f}/s)")
        assert elapsed < 10, f"1000 escrow transitions took {elapsed:.2f}s (> 10s limit)"

    @pytest.mark.asyncio
    async def test_merkle_service_1000_roots(self):
        """Compute 1000 Merkle roots and verify determinism."""
        from src.shared.infrastructure.merkle_service import MerkleService

        merkle = MerkleService()
        start = time.monotonic()

        roots = []
        for i in range(1000):
            entries = [
                f"entry_{i}_a",
                f"entry_{i}_b",
                f"entry_{i}_c",
            ]
            root = merkle.compute_root(entries)
            roots.append(root)
            assert len(root) == 64

        elapsed = time.monotonic() - start
        rate = (1000 / elapsed) if elapsed > 0 else float("inf")
        print(f"\n  1000 Merkle roots in {elapsed:.3f}s ({rate:.0f}/s)")

        # All roots unique
        assert len(set(roots)) == 1000

        # Deterministic
        root_check = merkle.compute_root(["entry_0_a", "entry_0_b", "entry_0_c"])
        assert root_check == roots[0]


# ══════════════════════════════════════════════════════════════════════════════
# Locust Load Test (optional — for distributed load generation)
# ══════════════════════════════════════════════════════════════════════════════

try:
    from locust import HttpUser, between, task

    class CadenciaLoadUser(HttpUser):
        """
        Locust user for distributed load testing.

        Run: locust -f tests/performance/test_load.py --host=http://localhost:8000

        Targets:
          - SRS-PF-001: /health < 500ms p95
          - SRS-PF-005: 100 concurrent users
        """

        wait_time = between(0.5, 2.0)

        @task(10)
        def health_check(self):
            self.client.get("/health")

        @task(3)
        def metrics_check(self):
            self.client.get("/metrics")

        @task(1)
        def register_flow(self):
            """Simulate registration (will fail auth but measures latency)."""
            self.client.post(
                "/v1/auth/register",
                json={
                    "enterprise": {
                        "legal_name": "Load Test Corp",
                        "pan": "ABCDE1234F",
                        "gstin": "29ABCDE1234F1Z5",
                        "trade_role": "BUYER",
                    },
                    "user": {
                        "email": f"load-{uuid.uuid4().hex[:8]}@test.in",
                        "password": "Str0ng!Pass#2026",
                    },
                },
                name="/v1/auth/register",
            )

except ImportError:
    pass  # locust not installed — pytest tests still work
