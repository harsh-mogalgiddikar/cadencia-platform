# Circuit breaker pattern for LLM and Algorand RPC resilience.
# context.md §9: prevent cascade failures from external service outages.

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Coroutine

from src.shared.domain.exceptions import DomainError
from src.shared.infrastructure.logging import get_logger

log = get_logger(__name__)


class CircuitOpenError(DomainError):
    """Raised when circuit is OPEN — service unavailable. Maps to HTTP 503."""

    error_code = "SERVICE_UNAVAILABLE"


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    In-process circuit breaker with Redis-backed state.

    States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing) → CLOSED
    """

    def __init__(
        self,
        name: str,
        redis: Any,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
    ) -> None:
        self.name = name
        self._redis = redis
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self._keys = {
            "state": f"cb:{name}:state",
            "failures": f"cb:{name}:failures",
            "last_failure": f"cb:{name}:last_failure",
            "successes": f"cb:{name}:successes",
        }

    async def get_state(self) -> CircuitState:
        """Get current circuit state, auto-transitioning OPEN → HALF_OPEN on timeout."""
        state_raw = await self._redis.get(self._keys["state"])
        if state_raw is None:
            return CircuitState.CLOSED

        state = CircuitState(
            state_raw.decode() if isinstance(state_raw, bytes) else state_raw
        )
        if state == CircuitState.OPEN:
            last_failure = await self._redis.get(self._keys["last_failure"])
            if last_failure:
                elapsed = time.time() - float(last_failure)
                if elapsed > self.recovery_timeout:
                    await self._redis.set(
                        self._keys["state"], CircuitState.HALF_OPEN.value
                    )
                    return CircuitState.HALF_OPEN
        return state

    async def call(self, coro: Coroutine) -> Any:  # type: ignore[type-arg]
        """Execute a coroutine through the circuit breaker."""
        state = await self.get_state()
        if state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit '{self.name}' is OPEN — service unavailable"
            )
        try:
            result = await coro
            await self._on_success()
            return result
        except CircuitOpenError:
            raise
        except Exception:
            await self._on_failure()
            raise

    async def _on_failure(self) -> None:
        failures = await self._redis.incr(self._keys["failures"])
        await self._redis.set(self._keys["last_failure"], str(time.time()))
        if int(failures) >= self.failure_threshold:
            await self._redis.set(self._keys["state"], CircuitState.OPEN.value)
            log.warning("circuit_opened", circuit=self.name, failures=int(failures))

    async def _on_success(self) -> None:
        state = await self.get_state()
        if state == CircuitState.HALF_OPEN:
            successes = await self._redis.incr(self._keys["successes"])
            if int(successes) >= self.success_threshold:
                await self._redis.delete(
                    self._keys["failures"],
                    self._keys["successes"],
                )
                await self._redis.set(
                    self._keys["state"], CircuitState.CLOSED.value
                )
                log.info("circuit_closed", circuit=self.name)
        elif state == CircuitState.CLOSED:
            # Reset failure count on success
            await self._redis.delete(self._keys["failures"])

    async def reset(self) -> None:
        """Force-reset circuit to CLOSED. For testing."""
        for key in self._keys.values():
            await self._redis.delete(key)


# Pre-configured breaker configs
LLM_CIRCUIT_CONFIG = {
    "failure_threshold": 5,
    "recovery_timeout": 60,
    "success_threshold": 2,
}

ALGORAND_CIRCUIT_CONFIG = {
    "failure_threshold": 3,
    "recovery_timeout": 30,
    "success_threshold": 2,
}
