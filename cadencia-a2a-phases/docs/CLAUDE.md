# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Cadencia** is an AI-native B2B trade marketplace for Indian MSMEs. It is a modular monolith with agentic automation — LLM agents negotiate trades, Algorand smart contracts settle payments, and a hash-chained audit log ensures regulatory compliance (FEMA/GST).

## Commands

### Development
```bash
docker-compose up                          # Start dev stack (Postgres+pgvector, Redis, Algorand localnet, FastAPI hot-reload)
docker-compose -f docker-compose.prod.yml up  # Production (Gunicorn 4 workers, Caddy HTTPS)
```

### Database
```bash
python scripts/migrate.py                  # Idempotent Alembic migration runner
```

### Smart Contracts (offline only — never compile at runtime)
```bash
algokit compile py contracts/escrow_contract.py --out-dir artifacts/
algokit compile py contracts/milestone_oracle.py --out-dir artifacts/
```

### Testing
```bash
pytest tests/unit/          # Pure domain tests (zero I/O, ≥90% coverage required)
pytest tests/integration/   # DB + Redis tests (requires Docker fixtures)
pytest tests/e2e/           # Full trade loop (requires Algorand localnet)
pytest tests/unit/path/to/test_file.py::TestClass::test_method  # Single test
```

### Linting & Type Checking (must pass on every PR)
```bash
ruff check .                # Zero violations required (rules: E, F, I, TID252)
mypy --strict .             # Zero errors required
```

## Architecture

### Seven-Layer Structure
```
Layer 1: Marketplace & Onboarding  — RFQ upload, LLM NLP extraction, pgvector matching
Layer 2: Agent Personalization     — strategy weights, history embeddings, playbooks
Layer 3: API Gateway               — FastAPI, JWT, rate limiting, CORS, SSE
Layer 4: Core Services             — NeutralEngine, SettlementService, ComplianceGenerator
Layer 5: Algorand Interaction      — Puya contracts, typed clients, dry-run safety
Layer 6: Data Layer                — PostgreSQL+pgvector, async SQLAlchemy, Redis, structlog
Layer 7: External Integrations     — Oracle, on/off-ramps, Frankfurter FX feed
```

### Source Layout
```
src/
├── shared/
│   ├── domain/          ← BaseEntity, BaseValueObject, DomainEvent, DomainError
│   ├── infrastructure/  ← DB session, Unit of Work, Redis, structlog
│   └── api/             ← Response envelopes, pagination, error handlers
├── identity/            ← Auth, KYC, enterprise management
├── marketplace/         ← RFQ lifecycle, pgvector matching, capability profiles
├── negotiation/         ← Agent sessions, offers, convergence/stall detection
├── settlement/          ← Escrow lifecycle, Algorand integration, Merkle service
├── compliance/          ← Hash-chained audit log, FEMA/GST export
└── treasury/            ← Liquidity pool, FX exposure (Frankfurter adapter)

contracts/               ← Puya smart contract source (.py)
artifacts/               ← Compiled TEAL + ARC-56 + typed clients (VCS-tracked)
tests/unit|integration|e2e/
main.py                  ← FastAPI app factory
```

### Bounded Context Internal Layout
Every bounded context (`identity/`, `marketplace/`, etc.) follows this structure:
```
domain/           ← Pure business logic; zero FastAPI/SQLAlchemy/algosdk imports
  entities/
  value_objects/
  policies/
  ports.py         ← Protocol interfaces (IRepository, IEngine, …)
application/      ← Commands, queries, application services
infrastructure/   ← SQLAlchemy models, external adapters (implement ports)
api/              ← FastAPI router + Pydantic request/response schemas
```

### Non-Negotiable Rules

| Rule | Enforcement |
|------|-------------|
| Domain layer MUST NOT import FastAPI, SQLAlchemy, algosdk, or any infrastructure | Ruff TID252 linting |
| Cross-domain communication ONLY via domain events — never direct imports between contexts | Ruff banned-module-imports |
| ALL smart contracts MUST be Algorand Python (Puya). **PyTeal is prohibited.** | CI `algokit compile py` |
| Smart contracts compiled **offline** only; compiled artifacts committed to VCS | CI compile step |
| EVERY Algorand call MUST be preceded by `algod.dryrun()`. Dry-run failure prevents broadcast and raises `BlockchainSimulationError` | `AlgorandGateway` implementation |
| `X402_SIMULATION_MODE=false` in production; `SIM-` prefixed tokens rejected everywhere | Code review + env check |
| All production data in **AWS ap-south-1 (Mumbai) only** | Infrastructure requirement |

### Key Patterns

**Hexagonal Architecture** — FastAPI is a delivery mechanism; PostgreSQL is a persistence adapter. All framework dependencies are at the edges, never in domain code.

**State Machines** (all transitions guarded by policy objects):
- KYC: `PENDING → KYC_SUBMITTED → VERIFIED → ACTIVE`
- RFQ: `DRAFT → PARSED → MATCHED → CONFIRMED → SETTLED`
- Negotiation: `ACTIVE → AGREED | FAILED | EXPIRED | HUMAN_REVIEW`
- Escrow: `DEPLOYED → FUNDED → RELEASED | REFUNDED` (orthogonal `FROZEN` flag)

**LLM Negotiation (NeutralEngine)** — Agents exchange offers round-by-round. Convergence ≤2% price gap triggers `SessionAgreed`. Stall at round threshold triggers `HUMAN_REVIEW`. All LLM prompts scanned for injection before calls.

**Vector Search** — RFQ embeddings use HNSW index (m=16, ef_construction=64); seller capability profiles use IVFFlat (lists=100, cosine). Target: Top-5 query < 2 s at 10K rows.

**Audit Trail** — SHA-256 hash-chained append-only audit log; Merkle root anchored on-chain after escrow release. Minimum 7-year retention.

### API Standards
- All endpoints versioned under `/v1/`
- Unified response envelope: `{success, data, error: {code, message, details}, request_id}`
- Cursor-based pagination (`CursorPage[T]`)
- SSE streams for real-time agent negotiation events

## Tech Stack Quick Reference

| Concern | Technology |
|---------|-----------|
| Language | Python 3.12+ (async-native) |
| Web framework | FastAPI 0.115+ / Uvicorn (Gunicorn in prod) |
| Database | PostgreSQL 16+ with pgvector 0.7+ |
| Cache / rate limiting | Redis 7.0+ |
| ORM | SQLAlchemy (async via asyncpg) |
| Validation | Pydantic v2 strict mode |
| Smart contracts | Algorand Python (Puya/PuyaPy) |
| Blockchain SDK | algosdk 2.x + algokit-utils 3.x |
| LLM providers | Pluggable — Google Gemini, Anthropic Claude, OpenAI |
| Linting | Ruff (E, F, I, TID252) |
| Type checking | Mypy strict |
| Logging | structlog (structured JSON, `request_id` on every line) |
| Reverse proxy | Caddy 2.x |
