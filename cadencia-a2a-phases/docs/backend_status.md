# Cadencia Backend — Implementation Status Audit

> Assessed against `context.md` (SRS/PRD/Architecture), April 2026.

---

## ✅ What IS Fully Done

### Core Domain Logic
| Domain | Status | Notes |
|---|---|---|
| **Identity** | ✅ Complete | Enterprise registration, JWT (RS256/HS256 fallback), refresh tokens, KYC state machine, RBAC `require_role()`, API keys (HMAC-SHA256 hashed) |
| **Negotiation Engine** | ✅ Complete | `NegotiationSession` DDD aggregate, full state machine (INIT→BUYER_ANCHOR→AGREED/FAILED/EXPIRED/HUMAN_REVIEW), offer rounds, convergence detection (≤2% gap), stall detection, human override, LLM agent driver, SSE streaming, playbook injection, opponent modeling, personalization |
| **Settlement / Escrow** | ✅ Complete | `Escrow` DDD aggregate, DEPLOYED→FUNDED→RELEASED/REFUNDED state machine, `AlgorandGateway` (deploy, fund, release, refund, freeze, unfreeze), dry-run safety enforcement, Merkle root anchoring via `AnchorService` |
| **Compliance** | ✅ Complete | Hash-chained `AuditEntry` (SHA-256 chain), `AuditChainVerifier`, FEMA Form A2 record generation, GST GSTR-2 record generation, `FEMAGSTExporter`, RLS Alembic migration (`004_compliance_rls.py`) |
| **Treasury** | ✅ Complete | `LiquidityPool`, `FXPosition`, `FrankfurterFXAdapter` (INR↔USDC, base URL fixed), dashboard, FX exposure, 30-day liquidity forecast |
| **Marketplace** | ✅ Complete | RFQ lifecycle (DRAFT→PARSED→MATCHED→CONFIRMED→SETTLED), LLM NLP parser, pgvector IVFFlat cosine similarity matchmaker, `CapabilityProfile`, embedding pipeline |

### Infrastructure & Cross-Cutting
| Component | Status | Notes |
|---|---|---|
| **Event Bus** | ✅ Complete | All 5 phases wired: `RFQConfirmed→CreateSession`, `SessionAgreed→DeployEscrow`, `EscrowDeployed/Funded/Released→Compliance`, HMAC-signed webhooks |
| **Hexagonal Architecture** | ✅ Complete | All 15 port interfaces implemented with concrete adapters; domain layer has no infrastructure imports |
| **Database** | ✅ Complete | 5 Alembic migrations (initial schema + settlement + compliance + RLS + agent memory), async SQLAlchemy, Unit of Work, pgvector indexes (IVFFlat + HNSW) |
| **Security** | ✅ Complete | RS256 JWT, HMAC-hashed API keys, `SecurityHeadersMiddleware` (HSTS, CSP, X-Frame-Options), CORS lockdown with wildcard guard, payload size limit (1MB), `reject_sim_tokens()`, `enforce_no_simulation_mode_at_startup()`, LLM prompt injection scanner, 8000-char input truncation |
| **Observability** | ✅ Complete | structlog (JSON, request_id per line), Prometheus metrics at `/metrics`, `prometheus-fastapi-instrumentator`, timing middleware, health check (`/health`) with DB/Redis/Algorand/LLM/circuit checks |
| **Smart Contract** | ✅ Complete | `CadenciaEscrow` in Algorand Python (Puya/PuyaPy), ARC-4 + ARC-56, compiled artifacts in `artifacts/` (TEAL + ARC56 JSON + typed client) |
| **CI/CD** | ✅ Present | `.github/workflows/ci.yml` + `rollback.yml` |
| **Docker** | ✅ Complete | `Dockerfile`, `Dockerfile.dev`, `docker-compose.yml` (dev), `docker-compose.prod.yml` (Gunicorn + Caddy), `Caddyfile`, `Caddyfile.prod` |
| **Test Suite** | ✅ Passing | **433 passed, 11 skipped, 0 failed** — unit, integration, E2E, performance suites all green |

---

## ⚠️ What Is Present But NOT Production-Grade Yet

These are the honest gaps between "code exists" and "ready for real traffic":

### 1. On/Off-Ramp (`MockOnRampAdapter` in production path)
- `src/settlement/api/dependencies.py` line 66: if `ONRAMP_PROVIDER` env var is unset or not `moonpay`, the **live settlement service uses `MockOnRampAdapter`** (fake INR↔USDC conversion).
- `MoonPayOnrampAdapter` exists (`src/settlement/infrastructure/moonpay_onramp_adapter.py`) but requires `MOONPAY_API_KEY` and `MOONPAY_SECRET_KEY` env vars.
- **Impact:** escrow funding via real INR fiat will not work until MoonPay credentials are configured and the provider is switched.

### 2. Algorand Dry-Run Enforcement is Code-Level Only
- `AlgorandGateway` calls `algod.dryrun()` — **but only when `ESCROW_DRY_RUN_ENABLED=true`**.
- A misconfigured production env without this flag bypasses the safety net.
- **Impact:** low risk if env is correct, but there's no startup enforcement check (unlike `X402_SIMULATION_MODE`).

### 3. SessionAgreed → Deploy: `wallet_address` field required
- `handle_session_agreed_deploy` in `handlers.py` correctly resolves wallet addresses from enterprise profiles, but the Identity domain only stores `algorand_wallet` if the enterprise explicitly provides it during KYC.
- If buyers/sellers register without providing an Algorand wallet address, **auto-escrow deployment silently skips** (logs a warning, does not raise).

### 4. KYC Adapter is Mocked
- `src/identity/infrastructure/kyc_adapter.py`: The `DigiLockerKYCAdapter` is scaffolded but uses no real DigiLocker API integration.
- KYC verification returns a mocked/passed status.
- **Impact:** Regulatory KYC compliance is not enforced in v1.

### 5. S3 Vault / Agent Memory Storage
- `src/negotiation/infrastructure/s3_vault.py` stores embeddings to S3 — requires `AWS_S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.
- Falls back gracefully if not configured, but agent personalization history **won't persist across restarts** without S3.

### 6. No Token Revocation / Blocklist
- The JWT `jti` (JWT ID) claim is minted but **no revocation store exists** (no Redis blocklist on logout).
- Refresh tokens cannot be individually revoked — only expiry provides protection.

### 7. Performance Targets Not Verified
- `context.md §15` specifies p95 < 500ms for API, p95 < 3000ms for LLM turns, p95 < 2000ms for pgvector.
- Performance tests exist (`tests/performance/`) for domain models but **no load test against a live server** has been run.

---

## ❌ What Is NOT Done (Genuinely Missing)

| Item | Priority | Notes |
|---|---|---|
| **Smoke tests against live staging** | High | `tests/smoke/test_production_smoke.py` exists but requires `SMOKE_TEST_BASE_URL` env var and a running server. Never been run against a real instance. |
| **FEMA/GST PDF generation** | Medium | `FEMAGSTExporter` generates structured records in DB but produces JSON/dict — **not actual PDF or CSV files** downloadable via the compliance endpoints. The API advertises PDF/CSV but returns JSON. |
| **S3 Glacier archival job** | Low | `context.md §11` specifies 7-year retention enforced via S3 Glacier archival job — the RLS policy exists but the archival scheduler does not. |
| **Weekly analytics report** | Low | `src/shared/infrastructure/analytics/weekly_report.py` exists but is not registered as a scheduled task anywhere. |
| **Milestone oracle for phased escrow release** | Low | `settlements` table exists but multi-milestone phased release (partial payment against delivery milestones) is not implemented in `SettlementService`. |

---

## Summary Verdict

```
Core backend: COMPLETE ✅
Production readiness: ~85% — needs MoonPay wiring, real KYC, smoke test run
Regulatory/compliance: ~70% — PDF/CSV export not real, KYC not wired
```

The codebase is **functionally complete for a prototype/testnet deployment**.
To go to production mainnet with real money and real MSMEs, the 3 gaps that need addressing first are:

1. ⚡ Wire `MoonPayOnrampAdapter` (set `ONRAMP_PROVIDER=moonpay` + API keys)
2. ⚡ Implement real PDF/CSV generation in `FEMAGSTExporter`
3. ⚡ Run smoke tests against a staging environment before mainnet
