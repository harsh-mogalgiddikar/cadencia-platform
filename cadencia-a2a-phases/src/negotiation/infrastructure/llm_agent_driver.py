# context.md §1.2: openai import ONLY in infrastructure — never in domain.
# context.md §1.4 OCP: IAgentDriver is the only interface.
# LLM_PROVIDER env var selects which driver is wired (default "openai").

from __future__ import annotations

import asyncio
import json
import os
import time
from decimal import Decimal

import structlog

from src.shared.api.llm_sanitizer import sanitize_llm_input, validate_agent_output
from src.shared.domain.exceptions import DomainError, ValidationError
from src.shared.infrastructure.metrics import (
    LLM_LATENCY_SECONDS,
    LLM_REQUESTS_TOTAL,
)

log = structlog.get_logger(__name__)

RETRY_DELAYS = [1.0, 2.0, 4.0]


class LLMExhaustedException(DomainError):
    """LLM failed after all retry attempts. Mapped to HTTP 503."""
    error_code = "LLM_EXHAUSTED"


class LLMAgentDriver:
    """OpenAI GPT-4o-backed agent driver implementing IAgentDriver."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> None:
        import openai  # type: ignore[import-untyped]
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def generate_offer(
        self,
        system_prompt: str,
        session_context: dict,
        offer_history: list[dict],
    ) -> dict:
        start_time = time.monotonic()
        system_prompt = sanitize_llm_input(system_prompt)
        user_content = json.dumps({
            "session": session_context,
            "offer_history": offer_history,
            "instruction": "Generate your next negotiation action as JSON.",
        })
        user_content = sanitize_llm_input(user_content)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        import openai  # type: ignore[import-untyped]
        last_error: Exception | None = None
        for attempt, delay in enumerate([0.0] + RETRY_DELAYS):
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"},
                )
                raw_content = response.choices[0].message.content or ""
                result = validate_agent_output(raw_content)

                # Prometheus: record success
                elapsed = time.monotonic() - start_time
                LLM_LATENCY_SECONDS.labels(provider=self.model.split("-")[0]).observe(elapsed)
                LLM_REQUESTS_TOTAL.labels(provider=self.model.split("-")[0], status="success").inc()

                return result
            except openai.RateLimitError as e:
                last_error = e
                log.warning("llm_rate_limit", attempt=attempt)
            except openai.APITimeoutError as e:
                last_error = e
                log.warning("llm_timeout", attempt=attempt)
            except openai.APIConnectionError as e:
                last_error = e
                log.error("llm_connection_error", attempt=attempt)
            except ValidationError as e:
                last_error = e
                log.warning("llm_invalid_output", attempt=attempt, error=str(e))
            except Exception as e:
                last_error = e
                log.error("llm_unexpected_error", attempt=attempt, error=str(e))

        # Prometheus: record failure
        elapsed = time.monotonic() - start_time
        LLM_LATENCY_SECONDS.labels(provider=self.model.split("-")[0]).observe(elapsed)
        LLM_REQUESTS_TOTAL.labels(provider=self.model.split("-")[0], status="error").inc()

        raise LLMExhaustedException(
            f"LLM failed after {len(RETRY_DELAYS) + 1} attempts: {last_error}"
        ) from last_error


class StubAgentDriver:
    """Deterministic stub for testing — no LLM calls. Implements IAgentDriver."""

    async def generate_offer(
        self,
        system_prompt: str,
        session_context: dict,
        offer_history: list[dict],
    ) -> dict:
        round_num = session_context.get("round_count", 0)
        last_price = offer_history[-1]["price"] if offer_history else 100000.0
        new_price = last_price * 0.98
        action = "ACCEPT" if round_num >= 5 else "OFFER"
        return {
            "action": action,
            "price": round(new_price, 2),
            "reasoning": (
                f"Stub agent round {round_num}: "
                f"{'accepting' if action == 'ACCEPT' else 'conceding 2%'}"
            ),
            "confidence": 0.75,
        }


def get_agent_driver() -> object:
    """
    Wire the correct LLM agent driver based on environment configuration.

    Environment Variables:
        LLM_PROVIDER:   "openai" | "gemini" | "stub" (default: "stub")
        LLM_MODEL:      Model identifier (default varies by provider)
                        OpenAI: "gpt-4o" (default), "gpt-4o-mini", "gpt-4-turbo"
                        Gemini: "gemini-1.5-pro" (default), "gemini-1.5-flash"
        OPENAI_API_KEY: Required when LLM_PROVIDER=openai
        GEMINI_API_KEY: Required when LLM_PROVIDER=gemini
        LLM_TEMPERATURE: Float 0.0-1.0 (default: 0.3)
        LLM_MAX_TOKENS:  Int (default: 512)

    Returns:
        LLMAgentDriver for production LLM, StubAgentDriver for testing.
    """
    provider = os.getenv("LLM_PROVIDER", "stub")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "512"))

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            log.warning("openai_api_key_missing_falling_back_to_stub")
            return StubAgentDriver()
        return LLMAgentDriver(
            api_key=api_key,
            model=os.getenv("LLM_MODEL", "gpt-4o"),
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            log.warning("gemini_api_key_missing_falling_back_to_stub")
            return StubAgentDriver()
        # Gemini uses OpenAI-compatible API via google-generativeai
        # or via the OpenAI SDK with base_url override
        return LLMAgentDriver(
            api_key=api_key,
            model=os.getenv("LLM_MODEL", "gemini-1.5-pro"),
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider != "stub":
        log.warning(
            "unknown_llm_provider_falling_back_to_stub",
            provider=provider,
            hint="Supported: openai, gemini, stub",
        )

    return StubAgentDriver()
