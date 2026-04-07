# Cadencia — Project Context Reference

> **Purpose:** This document is the single authoritative context file for Google Gemini (or any AI assistant) to reference before implementing any new phase, feature, or significant architectural change in the Cadencia codebase. Read this file in full before generating any code or making any architectural decision.

---

## 1. Product Vision

**Cadencia** is a closed-loop, AI-native agentic B2B trade marketplace purpose-built for Indian MSMEs (Micro, Small & Medium Enterprises). The platform collapses the entire B2B procurement lifecycle — vendor discovery, price negotiation, blockchain-secured escrow, settlement, and regulatory compliance export — into a single-upload autonomous workflow.

**Core Value Proposition:**
- A buyer uploads one RFQ (Request for Quotation) document.
- Cadencia autonomously handles: LLM NLP parsing → pgvector seller matching → AI agent negotiation → Algorand escrow deployment → settlement → FEMA/GST compliance record generation.
- Target: reduce procurement cycle from days → under 30 minutes for matched trades.

---

## 2. Target Users & Personas

| Persona | Role | Key Need |
|---|---|---|
| **A — MSME Buyer** | Procurement Manager | Upload RFQ; get ranked sellers; autonomous negotiation; compliance docs |
| **B — MSME Seller** | Sales / BD Manager | Receive pre-qualified leads; escrow-guaranteed payment |
| **C — Compliance Officer** | Internal/external auditor | Auto-generated FEMA Form A2 + GST GSTR-2 with 7-year retention |
| **D — Treasury Manager** | CFO / Treasury | Real-time INR/USDC pool balances, FX exposure, 30-day liquidity runway |

---

## 3. Non-Negotiable Architectural Principles

These are hard rules. Violating any of them is a breaking change regardless of context.

| Principle | Rule | Enforcement |
|---|---|---|
| **Puya-First Contracts** | ALL Algorand smart contracts MUST be written in Algorand Python (Puya/PuyaPy). PyTeal is explicitly PROHIBITED. | CI `algokit compile py` step |
| **Offline Contract Compilation** | Contracts are compiled offline: `algokit compile py contracts/escrow_contract.py --out-dir artifacts/`. Runtime compilation in production is PROHIBITED. | CI compile step |
| **Hexagonal Architecture** | The domain layer (`src/*/domain/`) MUST NOT import FastAPI, SQLAlchemy, algosdk, or any infrastructure library. | Ruff TID252 linting |
| **DDD Bounded Contexts** | Cross-domain communication occurs ONLY via domain events (`publisher.py`). Direct imports between bounded contexts are PROHIBITED. | Ruff banned-module-imports; Mypy strict |
| **No Simulation in Production** | `X402_SIMULATION_MODE` MUST be `false` in production. `SIM-` prefix tokens MUST be rejected in all code paths. | Code review + env check |
| **Dry-Run Before Every Chain Call** | Every Algorand contract call (deploy, fund, release, refund, freeze, unfreeze) MUST be preceded by `algod.dryrun()`. Dry-run failure MUST raise `BlockchainSimulationError` and PREVENT broadcast. | `AlgorandGateway` implementation |

---

## 4. System Architecture Overview

**Type:** API-first modular monolith
**API prefix:** `/v1/*`
**Deployment:** Containerised on AWS `ap-south-1` (Mumbai) — mandatory for data residency
**Reverse proxy:** Caddy 2.x (TLS via Let's Encrypt, HSTS, security headers)

### 4.1 Seven-Layer Architecture

| Layer | Name | Primary Responsibility |
|---|---|---|
| 1 | Marketplace & Onboarding | RFQ upload, LLM NLP field extraction, pgvector similarity matching, Top-N seller ranking |
| 2 | Agent Personalization Engine | AgentProfile storage, strategy weights, history embeddings, industry playbook injection |
| 3 | API Gateway | FastAPI routing, JWT validation, rate limiting, CORS, unified error envelope, SSE streaming |
| 4 | Core Services | NeutralEngine (negotiation), SettlementService (escrow), ComplianceGenerator (FEMA/GST) |
| 5 | Algorand Interaction | Puya contract typed client, algosdk integration, dry-run safety, Merkle anchoring |
| 6 | Data Layer | PostgreSQL 16 + pgvector, async SQLAlchemy, Unit of Work, Redis caching, structlog |
| 7 | External Integrations | Milestone oracle, INR↔USDC on/off-ramp, Frankfurter FX feed |

### 4.2 Bounded Contexts (DDD)

| Context | Responsibility | Key Aggregates | Key Ports |
|---|---|---|---|
| `identity` | Auth, KYC, enterprise management | Enterprise, User | IEnterpriseRepository, IUserRepository |
| `marketplace` | RFQ lifecycle, vector matching | RFQ, Match, CapabilityProfile | IRFQRepository, IMatchmakingEngine |
| `negotiation` | Agent sessions, offers | NegotiationSession, Offer, AgentProfile | ISessionRepository, INeutralEngine, IAgentDriver |
| `settlement` | Escrow, blockchain | Escrow, Settlement | IEscrowRepository, IBlockchainGateway, IMerkleService |
| `compliance` | Audit log, FEMA/GST | AuditLog, FEMARecord, GSTRecord | IAuditRepository, IComplianceExporter |
| `treasury` | Liquidity, FX | LiquidityPool, FXPosition | ILiquidityRepository, IFXProvider |

---

## 5. Tech Stack

| Component | Specification |
|---|---|
| Language | Python 3.12+ (async-native) |
| Framework | FastAPI 0.115+ with Uvicorn ASGI |
| Production server | Gunicorn (4 workers, `uvicorn.workers.UvicornWorker`) |
| Database | PostgreSQL 16+ with pgvector 0.7+ extension |
| Cache / Rate Limit | Redis 7.0+ |
| ORM | SQLAlchemy (async via asyncpg) |
| Blockchain SDK | algosdk 2.x + algokit-utils 3.x |
| Smart contracts | Algorand Python (Puya/PuyaPy), ARC-4 + ARC-56 |
| LLM providers | Google Gemini / Anthropic Claude / OpenAI (pluggable via `IAgentDriver` adapter) |
| Validation | Pydantic v2 (strict mode) |
| Linting | Ruff (E, F, I, TID252 rules) — zero violations on every CI build |
| Type checking | Mypy strict — zero errors on every CI build |
| Logging | structlog (structured JSON; request_id on every line) |
| Metrics | Prometheus at `/metrics` |
| Reverse proxy | Caddy 2.x |
| Containerization | Docker + Docker Compose |
| AWS Region | ap-south-1 (Mumbai) — mandatory |
| External FX Feed | Frankfurter API (INR ↔ USDC) |

---

## 6. External System Integrations

| External System | Integration Type | Direction | Purpose |
|---|---|---|---|
| Algorand Blockchain (testnet/mainnet) | algosdk + AlgoKit typed client | Bidirectional | Smart contract deploy, fund, release, refund; Merkle root anchoring |
| LLM Provider (Gemini/Claude/OpenAI) | HTTP REST (`IAgentDriver` adapter) | Outbound | RFQ NLP parsing; buyer/seller agent negotiation turns |
| KYC Provider | HTTP REST (`kyc_adapter`, mocked in v1) | Outbound | Enterprise KYC verification |
| Frankfurter FX Feed | HTTP REST (`fx_feed_adapter`) | Inbound | Live INR ↔ USDC rate for treasury dashboard |
| On/Off-Ramp Provider | HTTP REST (`IPaymentProvider`) | Bidirectional | INR ↔ USDC conversion for escrow funding |
| PostgreSQL 16 + pgvector | asyncpg (async SQLAlchemy) | Bidirectional | Primary data store; vector similarity search |
| Redis 7 | redis-py async | Bidirectional | Session caching; rate limiting; event state |

---

## 7. Domain Event Bus

All cross-domain communication happens via `publisher.py → handlers.py` (in-process event bus). Direct cross-context imports are PROHIBITED.

| Event | Publisher | Subscriber | Payload | Effect |
|---|---|---|---|---|
| `RFQConfirmed` | marketplace | negotiation | rfq_id, match_id, buyer_id, seller_id | CreateSession command dispatched |
| `SessionAgreed` | negotiation | settlement | session_id, agreed_price, buyer_addr, seller_addr | DeployEscrow command dispatched |
| `EscrowDeployed` | settlement | compliance | escrow_id, session_id, algo_app_id | AppendAuditEvent (ESCROW_DEPLOYED) |
| `EscrowFunded` | settlement | compliance | escrow_id, session_id, fund_tx_id | AppendAuditEvent (ESCROW_FUNDED) |
| `EscrowReleased` | settlement | compliance | escrow_id, session_id, release_tx_id, merkle_root | GenerateComplianceRecord (FEMA + GST) |
| `EscrowRefunded` | settlement | compliance | escrow_id, session_id, refund_tx_id, reason | AppendAuditEvent (ESCROW_REFUNDED) |
| `HumanOverride` | negotiation | negotiation | session_id, offer_id, original_price, override_price | Update AgentProfile weights |

---

## 8. End-to-End Trade Flow
Buyer uploads RFQ free-text
→ LLM NLP extraction (product, HSN, quantity, budget, delivery window, geography)
→ pgvector IVFFlat cosine similarity → Top-N ranked sellers returned
→ Buyer confirms preferred match → RFQConfirmed event
→ NegotiationSession created (status: ACTIVE)
→ Buyer + Seller LLM agents exchange offers (rounds)
→ Convergence (price gap ≤ 2%) → SessionAgreed event
→ OR Stall (rounds ≥ stall_threshold) → HUMAN_REVIEW
→ SettlementService deploys CadenciaEscrow on Algorand (dry-run first)
→ Buyer funds escrow (atomic PaymentTxn + AppCallTxn) → EscrowFunded event
→ Delivery confirmed → Admin releases escrow
→ Merkle root (SHA-256 hash chain of all audit events) anchored on-chain in Note field
→ EscrowReleased event → FEMA record + GST record auto-generated
→ Compliance officer downloads FEMA PDF / GST CSV
→ Merkle proof independently verifiable on-chain

text

---

## 9. State Machines

### 9.1 KYC State Machine
PENDING → KYC_SUBMITTED → VERIFIED → ACTIVE

text

### 9.2 RFQ State Machine
DRAFT → PARSED → MATCHED → CONFIRMED → SETTLED

text

### 9.3 Negotiation Session State Machine
ACTIVE → AGREED | FAILED | EXPIRED | HUMAN_REVIEW

text

### 9.4 Escrow State Machine
DEPLOYED(0) → FUNDED(1) → RELEASED(2) | REFUNDED(3)
FROZEN flag: orthogonal — prevents all state transitions while set

text

---

## 10. API Catalogue

**Global Standards:**
- All endpoints versioned under `/v1/`
- All responses use `ApiResponse[T]` envelope: `{success, data, error: {code, message, details}, request_id}`
- Pagination: cursor-based (`CursorPage[T]` with `next_cursor`, `has_more`)
- SSE stream: `Content-Type: text/event-stream`

### Authentication & Identity
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/v1/auth/register` | None | Register enterprise + admin user |
| POST | `/v1/auth/login` | None | Returns JWT access + refresh tokens |
| POST | `/v1/auth/refresh` | Refresh JWT | Rotate access token |
| POST | `/v1/auth/api-keys` | JWT | Create API key for M2M |
| DELETE | `/v1/auth/api-keys/{key_id}` | JWT | Revoke API key |
| GET | `/v1/enterprises/{id}` | JWT | Get enterprise profile |
| PATCH | `/v1/enterprises/{id}/kyc` | JWT | Submit KYC documents |
| PUT | `/v1/enterprises/{id}/agent-config` | JWT | Update agent personalization config |

### Marketplace
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/v1/marketplace/rfq` | JWT | Upload RFQ (triggers NLP + matching) |
| GET | `/v1/marketplace/rfq/{id}` | JWT | Get RFQ with parsed fields + match list |
| GET | `/v1/marketplace/rfq/{id}/matches` | JWT | Get ranked match list |
| POST | `/v1/marketplace/rfq/{id}/confirm` | JWT | Confirm RFQ, select match, initiate negotiation |
| PUT | `/v1/marketplace/capability-profile` | JWT | Update seller capability profile |
| POST | `/v1/marketplace/capability-profile/embeddings` | JWT | Recompute embeddings via LLM |

### Negotiation Sessions
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/v1/sessions` | JWT | Create session from confirmed match |
| GET | `/v1/sessions/{id}` | JWT | Get session state + offer history |
| GET | `/v1/sessions/{id}/stream` | JWT | SSE stream — live agent turn events |
| POST | `/v1/sessions/{id}/override` | JWT | Human override: inject offer mid-session |
| POST | `/v1/sessions/{id}/terminate` | JWT | Admin-terminate session |

### Escrow
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/v1/escrow/{session_id}` | JWT | Get escrow state + Algorand app info |
| POST | `/v1/escrow/{id}/fund` | JWT | Fund escrow (atomic PaymentTxn + AppCall) |
| POST | `/v1/escrow/{id}/release` | JWT | Release funds to seller with Merkle root |
| POST | `/v1/escrow/{id}/refund` | JWT | Refund buyer |
| POST | `/v1/escrow/{id}/freeze` | JWT | Freeze escrow during dispute |

### Audit, Compliance & Treasury
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/v1/audit/log` | JWT (AUDITOR) | Paginated audit log |
| GET | `/v1/audit/proof/{session_id}` | JWT | Merkle proof for session audit trail |
| GET | `/v1/compliance/fema/{session_id}` | JWT | FEMA record download (PDF/CSV) |
| GET | `/v1/compliance/gst/{session_id}` | JWT | GST reconciliation record download |
| POST | `/v1/compliance/export` | JWT | Bulk compliance export (date range) |
| GET | `/v1/treasury/dashboard` | JWT (TREASURY_MANAGER) | Pool balances + FX rate |
| GET | `/v1/treasury/fx-exposure` | JWT | Open FX position summary |
| GET | `/v1/treasury/liquidity-forecast` | JWT | 30-day liquidity runway |
| GET | `/metrics` | Internal only | Prometheus metrics |
| GET | `/health` | None | DB + Redis + Algorand health check |

### HTTP Error Code Mapping
| Domain Error | HTTP Status | Error Code |
|---|---|---|
| NotFoundError | 404 | NOT_FOUND |
| PolicyViolation | 422 | POLICY_VIOLATION |
| ValidationError | 422 | VALIDATION_ERROR |
| RateLimitError | 429 | RATE_LIMIT_EXCEEDED |
| BlockchainSimulationError | 502 | BLOCKCHAIN_DRY_RUN_FAILED |
| AuthenticationError | 401 | UNAUTHORIZED |
| AuthorizationError | 403 | FORBIDDEN |
| UnexpectedError | 500 | INTERNAL_ERROR |

---

## 11. Database Schema

| Table | Domain | Primary Key | Key Columns | Indexes |
|---|---|---|---|---|
| `enterprises` | identity | UUID | pan (unique), gstin (unique), kyc_status, trade_role, algorand_wallet | PK, pan_idx, gstin_idx |
| `users` | identity | UUID | enterprise_id (FK), email (unique), role, password_hash | PK, email_idx |
| `api_keys` | identity | UUID | enterprise_id (FK), key_hash (unique), is_active, expires_at | PK, key_hash_idx |
| `rfqs` | marketplace | UUID | enterprise_id (FK), status, hsn_code, budget_min, budget_max, embedding (vector 1536) | PK, enterprise_status_idx, HNSW |
| `capability_profiles` | marketplace | UUID | enterprise_id (FK unique), embedding (vector 1536), commodities[] | PK, IVFFlat |
| `matches` | marketplace | UUID | rfq_id (FK), seller_enterprise_id (FK), score (float), rank | PK, rfq_idx |
| `negotiation_sessions` | negotiation | UUID | rfq_id, match_id, buyer_enterprise_id, seller_enterprise_id, status, agreed_price | PK, rfq_idx, status_idx |
| `offers` | negotiation | UUID | session_id (FK), round_number, proposer_role, price, confidence, is_human_override | PK, session_round_idx |
| `agent_profiles` | negotiation | UUID | enterprise_id (FK unique), risk_profile (JSONB), automation_level, strategy_weights (JSONB) | PK |
| `escrow_contracts` | settlement | UUID | session_id (FK unique), algo_app_id (bigint unique), amount_microalgo, status, merkle_root | PK, session_idx, app_id_idx |
| `settlements` | settlement | UUID | escrow_id (FK), milestone_index, amount_microalgo, tx_id, oracle_confirmation (JSONB) | PK, escrow_idx |
| `audit_log` | compliance | UUID | enterprise_id (FK), session_id, event_type, event_data (JSONB), prev_hash, entry_hash | enterprise_created_idx |
| `compliance_records` | compliance | UUID | enterprise_id (FK), session_id (FK), record_type (FEMA/GST), record_data (JSONB) | PK, enterprise_type_idx |

### Vector Index Configuration
- `capability_profiles.embedding`: **IVFFlat**, cosine distance, lists=100. Target: Top-5 query < 2s at 10,000 rows.
- `rfqs.embedding`: **HNSW** (pgvector ≥ 0.5.0), m=16, ef_construction=64.
- Embeddings: 1536-dimensional float32.

### Data Retention Policy
| Table | Retention | Enforcement |
|---|---|---|
| audit_log | Minimum 7 years | PostgreSQL row-level security + S3 Glacier archival job |
| compliance_records | Minimum 7 years | Same as audit_log |
| offers | Minimum 3 years | Soft-delete with `archived_at` |
| negotiation_sessions | Minimum 3 years | Soft-delete with `completed_at` |
| escrow_contracts | Permanent | Never deleted; on-chain Merkle root provides proof |

---

## 12. Smart Contract Specification

### CadenciaEscrow Contract

| Field | Value |
|---|---|
| **Language** | Algorand Python (Puya/PuyaPy) |
| **ABI Standard** | ARC-4 + ARC-56 |
| **Source file** | `contracts/escrow_contract.py` |
| **Compiled output** | `artifacts/CadenciaEscrow.approval.teal`, `.clear.teal`, `.arc56.json`, `CadenciaEscrowClient.py` |
| **Compilation** | `algokit compile py contracts/escrow_contract.py --out-dir artifacts/` (offline only) |

### Global State Variables
| Variable | Type | Description |
|---|---|---|
| `buyer` | Account (bytes[32]) | Algorand address of buyer enterprise |
| `seller` | Account (bytes[32]) | Algorand address of seller enterprise |
| `amount` | UInt64 | Escrow amount in microALGO |
| `session_id` | Bytes | Cadencia negotiation session UUID |
| `status` | UInt64 | 0=DEPLOYED, 1=FUNDED, 2=RELEASED, 3=REFUNDED |
| `frozen` | UInt64 | 0=normal, 1=frozen (no transitions permitted) |

### ABI Methods

| Method | Access Control | Pre-condition | Post-condition |
|---|---|---|---|
| `initialize(buyer, seller, amount, session_id)` | Creator only (CREATE) | None | status=0, frozen=0 |
| `fund(payment: PaymentTransaction)` | Any (buyer) | status==0, frozen==0, payment.amount==self.amount | status=1 |
| `release(merkle_root: String)` | Creator only | status==1, frozen==0 | status=2; inner payment to seller |
| `refund(reason: String)` | Creator only | status==1 | status=3; inner payment to buyer |
| `freeze()` | buyer OR seller OR creator | Any status | frozen=1 |
| `unfreeze()` | Creator only | frozen==1 | frozen=0 |

### Smart Contract Safety Rules
- `SRS-SC-001`: ALL contract calls MUST be preceded by `algod.dryrun()`. Failure → `BlockchainSimulationError` → no broadcast.
- `SRS-SC-002`: `fund()` verifies `payment.amount == self.amount` atomically. Any mismatch fails the group.
- `SRS-SC-003`: `release()` and `refund()` assert `frozen==0`.
- `SRS-SC-004`: Only the contract creator may call `release()`, `refund()`, or `unfreeze()`.
- `SRS-SC-006`: Transaction submission is idempotent via algosdk tx ID deduplication — zero double-spend risk.

---

## 13. Port Interface Catalogue

| Interface | Context | Concrete Adapter | Key Methods |
|---|---|---|---|
| `IEnterpriseRepository` | identity | PostgresEnterpriseRepository | get, save, find_by_pan, find_by_gstin |
| `IUserRepository` | identity | PostgresUserRepository | get, get_by_email, save |
| `IRFQRepository` | marketplace | PostgresRFQRepository | get, save, list_for_enterprise |
| `IMatchmakingEngine` | marketplace | pgvector_matchmaker | find_top_n_matches(rfq_embedding, n) → List[Match] |
| `IDocumentParser` | marketplace | LLMDocumentParser | parse(raw_text) → ParsedRFQFields |
| `ISessionRepository` | negotiation | PostgresSessionRepository | get, save, list_active |
| `INeutralEngine` | negotiation | NeutralEngine | run_round(session, buyer_agent, seller_agent) → RoundResult |
| `IAgentDriver` | negotiation | LLMAgentDriver | generate_offer(role, session_ctx, profile) → AgentAction |
| `IEscrowRepository` | settlement | PostgresEscrowRepository | get, get_by_session, save |
| `IBlockchainGateway` | settlement | AlgorandGateway | deploy_escrow, fund_escrow, release_escrow, refund_escrow, freeze_escrow, unfreeze_escrow |
| `IMerkleService` | settlement | MerkleService | compute_root(entries) → MerkleRoot, generate_proof(entry, entries) → MerkleProof |
| `IPaymentProvider` | settlement | OnRampAdapter | convert_inr_to_usdc, convert_usdc_to_inr |
| `IAuditRepository` | compliance | PostgresAuditRepository | append, get_log, get_chain |
| `IComplianceExporter` | compliance | FEMAGSTExporter | export_fema(session_id), export_gst(session_id) |
| `IFXProvider` | treasury | FrankfurterFXAdapter | get_rate(base, target) → FXRate |

---

## 14. Security Requirements (Hard Rules)

### Authentication
- JWT access tokens: **RS256-signed**, 15-minute expiry. HS256 is PROHIBITED.
- Refresh tokens: **httpOnly, Secure, SameSite=Strict** cookies, 30-day expiry.
- API keys: stored as **HMAC-SHA256 hashes**. Plaintext NEVER persisted or logged.
- Every protected route MUST call `require_role()` before business logic.
- CORS locked to `CORS_ALLOWED_ORIGINS` env var. Wildcard `*` origins PROHIBITED in production.

### LLM Security
- ALL RFQ text and capability profile inputs MUST be scanned for prompt injection before LLM call.
- LLM inputs hard-truncated at **8,000 characters**.
- Agent JSON output MUST be validated: `action ∈ {OFFER, ACCEPT, REJECT, COUNTER}`, price numeric. Non-conforming output → `ValidationError`, turn does not advance.

### Blockchain Security
- Algorand escrow creator mnemonic: **environment variable ONLY**. Never in VCS, logs, or error messages.
- `X402_SIMULATION_MODE=false` in production. `SIM-` prefix tokens rejected everywhere.
- Outbound settlement webhooks: signed with **HMAC-SHA256** (`X-Cadencia-Signature` header).

### Data Security
- Zero secrets in VCS — all in environment variables.
- structlog: mask sensitive fields (passwords, mnemonics, API keys) before logging.
- Production DB: TLS in transit (`DATABASE_URL` with `ssl=require`).
- Caddy: TLS (Let's Encrypt), HSTS (`max-age=63072000`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`.
- Data residency: **AWS ap-south-1 (Mumbai)**. No production data outside ap-south-1.

---

## 15. Non-Functional Requirements

### Performance Targets
| Requirement | Metric | Target |
|---|---|---|
| API response latency | p95 (non-blockchain) | < 500ms |
| Agent negotiation turn | p95 (LLM + policy + DB write) | < 3,000ms |
| pgvector matching | p95 (Top-5 across 10K profiles) | < 2,000ms |
| Algorand finality detection | Block event lag | < 5,000ms |
| Concurrent sessions (prototype) | Simultaneous active | 100 |
| Concurrent sessions (Phase 2) | Simultaneous active | 1,000 |
| LLM throughput cap | Redis rate limit | 50 req/min |
| API rate limit per enterprise | Redis sliding window | 100 req / 60s |

### Reliability Targets
- Escrow deployment success: ≥ 99.5% testnet / ≥ 99.9% mainnet
- Audit trail hash-chain integrity: 100% — zero hash breaks tolerated
- Transaction idempotency: zero double-spend incidents
- Unit of Work atomicity: 100% — no partial commits

### Maintainability Rules
- Mypy strict: zero errors on every CI build.
- Ruff (E, F, I, TID252): zero violations on every CI build.
- Domain unit tests: ≥ 90% line coverage on all `domain/` directories.
- Application unit tests: ≥ 80% line coverage on `application/` directories.
- All new port implementations MUST pass Mypy Protocol conformance.
- Alembic migrations: idempotent; `scripts/migrate.py` safe to run on container start.
- Zero hardcoded config in application code — all via environment variables.

---

## 16. Deployment & Infrastructure

### Docker Compose Configurations
| Config | Purpose | Key Services |
|---|---|---|
| `docker-compose.yml` | Local development | PostgreSQL 16+pgvector, Redis 7, Algorand localnet, FastAPI hot-reload |
| `docker-compose.prod.yml` | Production | Gunicorn (4 workers), Caddy HTTPS, health checks, no localnet |

### CI/CD Pipeline (Required on Every PR/Merge)
- Ruff linting (E, F, I, TID252) — must pass on every PR
- Mypy strict — must pass on every PR
- Domain unit tests (pytest, zero I/O) — must pass on every PR
- Puya compile (`algokit compile py`) on every `contracts/` change; `artifacts/` committed
- Integration tests (pytest + testcontainers) on merge to `main`
- Alembic migration dry-run on every `alembic/versions/` change
- Docker image build on every merge to `main` (tagged with git SHA)

### Health Check
`GET /health` → HTTP 200 when healthy:
```json
{
  "status": "healthy",
  "db": "connected",
  "redis": "connected",
  "algorand": "connected",
  "version": "3.0.0"
}
```
Any failing dependency → HTTP 503 with failing component identified.

---

## 17. Environment Variables Reference

| Variable | Purpose | Notes |
|---|---|---|
| `DATABASE_URL` | PostgreSQL async connection string | Must include `ssl=require` in prod |
| `REDIS_URL` | Redis connection string | e.g. `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | RS256 signing key | NEVER commit to VCS |
| `ALGORAND_NETWORK` | Target network | `testnet` or `mainnet` |
| `ALGORAND_ESCROW_CREATOR_MNEMONIC` | 25-word Algorand mnemonic | NEVER commit to VCS |
| `LLM_PROVIDER` | LLM backend selector | `google` / `anthropic` / `openai` |
| `ESCROW_DRY_RUN_ENABLED` | Dry-run before all chain calls | Always `true` in non-production |
| `X402_SIMULATION_MODE` | Payment simulation mode | MUST be `false` in production |
| `CORS_ALLOWED_ORIGINS` | Allowed CORS origins | No wildcards in production |
| `AUDIT_RETENTION_YEARS` | Minimum audit log retention | `7` |
| `DATA_RESIDENCY_REGION` | AWS data residency | `ap-south-1` |

---

## 18. Development Phase Roadmap

| Phase | Timeline | Deliverable | Exit Criteria |
|---|---|---|---|
| **Phase 0 — Foundation** | Week 1 | Bootable platform | `docker compose up` boots; `/health` returns 200; Puya contract compiled to `artifacts/` |
| **Phase 1 — Identity & Auth** | Weeks 1–2 | Auth system live | JWT auth complete; rate limiting active; unit tests passing |
| **Phase 2 — Algorand Escrow** | Weeks 2–3 | Escrow lifecycle on localnet | Full deploy → fund → release → refund verified with dry-run |
| **Phase 3 — Audit & x402** | Week 3 | Immutable audit log | Hash-chained AuditLog verifiable; Merkle proof endpoint working |
| **Phase 4 — Negotiation Engine** | Weeks 3–4 | Autonomous negotiation | LLM agents complete; SSE stream emits all events; human override persisted |
| **Phase 5 — Marketplace** | Weeks 4–5 | Full RFQ-to-trade loop | RFQ → NLP parse → pgvector match → confirm → session handoff end-to-end |
| **Phase 6 — Compliance** | Week 5 | Compliance auto-generation | Every test trade generates FEMA + GST records downloadable as PDF/CSV |
| **Phase 7 — Production Hardening** | Week 6 | Production-ready platform | `docker-compose.prod.yml` fully operational; all endpoints < 500ms p95 |

---

## 19. Critical Test Cases

| Test ID | Description | Expected Result |
|---|---|---|
| TC-001 | test_budget_guard_rejects_over_ceiling | Offer > budget_ceiling → PolicyViolation; session does not advance |
| TC-002 | test_stall_detection_triggers_human_review | round_count ≥ stall_threshold → HUMAN_REVIEW |
| TC-003 | test_convergence_detection_agrees_session | Price gap ≤ 2% → AGREED; SessionAgreed event emitted |
| TC-004 | test_dry_run_failure_prevents_broadcast | BlockchainSimulationError raised; no broadcast; escrow status unchanged |
| TC-005 | test_escrow_fund_partial_amount_rejected | payment.amount ≠ escrow.amount → transaction group fails |
| TC-006 | test_frozen_escrow_rejects_release | release() on frozen escrow → ContractAssertionError; status unchanged |
| TC-007 | test_audit_log_hash_chain_integrity | SHA-256(prev_hash + event_data) matches stored entry_hash for all entries |
| TC-008 | test_prompt_injection_rejected_before_llm | Injection detected → ValidationError; LLM adapter not called |
| TC-009 | test_agent_output_non_json_raises_error | Non-JSON agent output → ValidationError; turn not persisted |
| TC-010 | test_complete_trade_loop_e2e | RFQ → match → confirm → agree → escrow → fund → release → FEMA+GST generated on localnet |

---

## 20. Key Glossary

| Term | Definition |
|---|---|
| RFQ | Request for Quotation — primary trade initiation document uploaded by a buyer |
| HSN Code | Harmonised System of Nomenclature — mandatory goods classification code for GST |
| MSME | Micro, Small & Medium Enterprise — primary target user |
| FEMA | Foreign Exchange Management Act — Indian regulation governing cross-border payments |
| GST / GSTIN | Goods and Services Tax / 15-character GSTIN identifier |
| PAN | 10-character Indian tax identifier (format: AAAAA9999A) |
| Puya / PuyaPy | Algorand Foundation's Python-based smart contract language (successor to PyTeal) |
| ARC-4 | Algorand ABI specification for typed smart contract method calls |
| ARC-56 | Extended Algorand contract metadata for typed client generation |
| AlgoKit | Algorand developer toolkit (compile, deploy, test) |
| pgvector | PostgreSQL extension for vector embeddings and similarity search |
| IVFFlat | Approximate nearest-neighbour index type in pgvector (cosine similarity) |
| HNSW | Hierarchical Navigable Small World — pgvector index for RFQ embeddings |
| SSE | Server-Sent Events — HTTP streaming for real-time negotiation turn events |
| DDD | Domain-Driven Design — organise code by business domain |
| Hexagonal | Ports and Adapters architecture isolating domain logic from infrastructure |
| UoW | Unit of Work — ensures atomic DB commits across repository operations |
| JWT | JSON Web Token — RS256-signed bearer token for API authentication |
| HMAC | Hash-Based Message Authentication Code — API key storage and webhook signing |
| Merkle root | SHA-256 cryptographic commitment to all session audit records, anchored on-chain |
| Dry-run | Algorand transaction simulation via `algod.dryrun()` before broadcast |
| microALGO | Algorand base unit (1 ALGO = 1,000,000 microALGO) |
| LLM | Large Language Model — used for NLP parsing and agent negotiation |

---

*Document source: Cadencia PRD v1.0 + SRS v1.0 (IEEE 830-Compatible), April 2026*
*Architecture version: Production Backend v3.0*