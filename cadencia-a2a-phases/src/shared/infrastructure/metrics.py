"""
Prometheus metric definitions for Cadencia.

context.md §5: Prometheus at /metrics for observability.
context.md §10: GET /metrics — internal only (blocked by Caddy externally).
SRS §10.5: Five mandatory custom metrics with exact names.

Custom business metrics beyond the auto-instrumented HTTP metrics
provided by prometheus-fastapi-instrumentator.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ══════════════════════════════════════════════════════════════════════════════
# SRS §10.5 — MANDATORY METRICS (exact names from specification)
# ══════════════════════════════════════════════════════════════════════════════

# SRS §10.5.1: cadencia_active_sessions — Gauge
ACTIVE_SESSIONS = Gauge(
    "cadencia_active_sessions",
    "Number of currently active negotiation sessions",
)

# SRS §10.5.2: cadencia_escrow_state_total — Counter (labeled by state)
ESCROW_STATE_TOTAL = Counter(
    "cadencia_escrow_state_total",
    "Total escrow state transitions",
    ["state"],  # "DEPLOYED", "FUNDED", "RELEASED", "REFUNDED", "FROZEN"
)

# SRS §10.5.3: cadencia_llm_latency_seconds — Histogram (labeled by provider)
LLM_LATENCY_SECONDS = Histogram(
    "cadencia_llm_latency_seconds",
    "LLM API call latency by provider",
    ["provider"],  # "openai", "gemini", "stub"
    buckets=(0.5, 1, 2, 3, 5, 10, 20, 30, 60),
)

# SRS §10.5.4: cadencia_api_request_duration_seconds — Histogram
# NOTE: Auto-instrumented by prometheus-fastapi-instrumentator in main.py.
# The instrumentator registers http_request_duration_seconds by default.
# We keep this alias for SRS compliance if needed by dashboards.

# SRS §10.5.5: cadencia_rate_limit_hits_total — Counter
RATE_LIMIT_HITS_TOTAL = Counter(
    "cadencia_rate_limit_hits_total",
    "Total rate limit rejections (HTTP 429)",
)

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN-SPECIFIC METRICS (beyond SRS §10.5 minimum)
# ══════════════════════════════════════════════════════════════════════════════

# ── Negotiation ───────────────────────────────────────────────────────────────

NEGOTIATION_ROUNDS_TOTAL = Counter(
    "cadencia_negotiation_rounds_total",
    "Total negotiation rounds completed",
    ["outcome"],  # "offer", "counter", "accept", "reject", "timeout", "stall"
)

NEGOTIATION_SESSION_DURATION = Histogram(
    "cadencia_negotiation_session_duration_seconds",
    "Duration of negotiation sessions from creation to terminal state",
    buckets=(5, 15, 30, 60, 120, 300, 600, 1800, 3600),
)

# ── Escrow ────────────────────────────────────────────────────────────────────

ESCROW_DEPLOY_DURATION = Histogram(
    "cadencia_escrow_deploy_duration_seconds",
    "Time taken to deploy an escrow contract on Algorand",
    buckets=(1, 2, 5, 10, 20, 30, 60),
)

ESCROW_FUND_AMOUNT = Histogram(
    "cadencia_escrow_fund_amount_microalgo",
    "Distribution of escrow funding amounts in microALGO",
    buckets=(100_000, 1_000_000, 10_000_000, 50_000_000, 100_000_000, 500_000_000),
)

# ── LLM ───────────────────────────────────────────────────────────────────────

LLM_REQUESTS_TOTAL = Counter(
    "cadencia_llm_requests_total",
    "Total LLM API calls",
    ["provider", "status"],  # provider: "openai", "gemini", "stub"; status: "success", "error"
)

# ── Circuit Breaker ───────────────────────────────────────────────────────────

CIRCUIT_BREAKER_STATE = Gauge(
    "cadencia_circuit_breaker_state",
    "Circuit breaker state by service (0=CLOSED, 1=HALF_OPEN, 2=OPEN)",
    ["service"],  # "algorand", "llm", "frankfurter"
)

# ── Marketplace ───────────────────────────────────────────────────────────────

RFQ_UPLOADS_TOTAL = Counter(
    "cadencia_rfq_uploads_total",
    "Total RFQ uploads",
    ["status"],  # "success", "validation_error"
)

VECTOR_SEARCH_DURATION = Histogram(
    "cadencia_vector_search_duration_seconds",
    "pgvector similarity search latency",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

# ── Treasury ──────────────────────────────────────────────────────────────────

FX_RATE_UPDATES_TOTAL = Counter(
    "cadencia_fx_rate_updates_total",
    "Total FX rate fetches from Frankfurter",
    ["source"],  # "api", "cache", "mock"
)

ONRAMP_CONVERSIONS_TOTAL = Counter(
    "cadencia_onramp_conversions_total",
    "Total on/off-ramp currency conversions",
    ["direction"],  # "inr_to_usdc", "usdc_to_inr"
)
