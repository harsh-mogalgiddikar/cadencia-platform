# Cadencia Prototype Presentation Rundown

---

## 1. What to Spin Up

```bash
# One command to boot everything locally
docker-compose up -d
```

This gives you:
- **PostgreSQL 16 + pgvector** — full schema via Alembic auto-migration
- **Redis 7** — rate limiting + session cache
- **Algorand localnet** — fake ALGO, instant finality, free testnet wallet
- **FastAPI** — hot-reload, `/docs` Swagger UI available at `localhost:8000/docs`

Verify it's healthy:
```bash
curl http://localhost:8000/health
# → {"status":"healthy","db":"ok","redis":"ok","algorand":"ok"}
```

---

## 2. The Demo Script (8 Steps, ~15 min)

Walk through this **exact flow** — it maps directly to your PRD's "under 30 minutes from upload to settlement" claim.

### Step 1 — Register Buyer + Seller (30 sec)
```bash
POST /v1/auth/register   # buyer: Buyer Exports Pvt Ltd (role: BUYER)
POST /v1/auth/register   # seller: Seller Mfg Pvt Ltd (role: SELLER)
```
**Talk track:** *"Any MSME registers once — GST, PAN, trade role, commodity list. That's their identity on-chain and in the marketplace."*

### Step 2 — Upload RFQ (1 min)
```bash
POST /v1/marketplace/rfq
# body: free-text "Need 500 bundles of organic cotton, HSN 5201,
#        budget ₹4-5 lakh, delivery Mumbai within 30 days"
```
Show the response — LLM has extracted: `hsn_code`, `quantity`, `budget_min/max`, `delivery_days`, `geography`.

**Talk track:** *"One document upload. The LLM parses it — no forms, no manual entry."*

### Step 3 — Vector Match (30 sec)
```bash
GET /v1/marketplace/rfq/{id}/matches
# → Top-5 sellers ranked by cosine similarity score
```
Show the score (e.g. `0.94`) and why that seller matched (commodity overlap, capacity).

**Talk track:** *"pgvector similarity search across all registered sellers. Returns a ranked shortlist in milliseconds."*

### Step 4 — Confirm Match → Trigger Negotiation (30 sec)
```bash
POST /v1/marketplace/rfq/{id}/confirm
# → RFQConfirmed event fires → NegotiationSession created automatically
```
This fires the `RFQConfirmed` domain event. The event bus wires it directly to session creation — no manual step.

### Step 5 — Watch AI Agents Negotiate in Real-Time (5 min, the wow moment)
```bash
GET /v1/sessions/{id}/stream   # SSE stream
```
Open this in a browser (or use `curl -N`). You'll see live events:
```
data: {"role":"BUYER","price":420000,"confidence":0.85,"reasoning":"Anchoring low based on market index"}
data: {"role":"SELLER","price":510000,"confidence":0.80,"reasoning":"Margin protection - cotton futures up 3%"}
data: {"role":"BUYER","price":478000,"confidence":0.91,"reasoning":"Converging — within 2% tolerance"}
data: {"event":"SESSION_AGREED","agreed_price":478000}
```
**Talk track:** *"Two LLM agents, one for buyer, one for seller, negotiating on behalf of their enterprise. No human in the loop. Convergence in 3 rounds."*

### Step 6 — Escrow Deploys Automatically (1 min)
After `SessionAgreed`, the event bus fires `DeployEscrowCommand` automatically:
```bash
GET /v1/escrow/{session_id}
# → {"status":"DEPLOYED","algo_app_id":12345678,"amount_microalgo":478000000}
```
**Talk track:** *"The moment both agents agree, a smart contract deploys on Algorand. No human approves it — it just happens."*

### Step 7 — Release + Merkle Proof (1 min)
```bash
POST /v1/escrow/{id}/release
GET /v1/audit/proof/{session_id}
# → {"merkle_root":"a3f9...","proof":[...],"verifiable_on_chain":true}
```
**Talk track:** *"Every event in the trade — RFQ, negotiation rounds, escrow — is hashed into a Merkle tree and anchored on-chain. Anyone can independently verify the audit trail."*

### Step 8 — Compliance Records Auto-Generated (1 min)
```bash
GET /v1/compliance/fema/{session_id}
GET /v1/compliance/gst/{session_id}
```
**Talk track:** *"FEMA Form A2 and GST reconciliation records generated automatically. The compliance officer downloads them — they don't fill them in."*

---

## 3. What to Have Ready Before the Demo

| Prep item | Why |
|---|---|
| Pre-seeded buyer + seller accounts with `algorand_wallet` addresses | So Step 6 (auto-deploy) fires without skipping |
| Localnet funded wallet | So escrow has ALGO to move |
| LLM API key set (`LLM_PROVIDER=google`, `GOOGLE_API_KEY=...`) | So negotiation runs with real AI |
| Swagger UI open at `localhost:8000/docs` | Shows the full API surface at a glance |
| Terminal with `curl -N localhost:8000/v1/sessions/{id}/stream` ready | SSE live stream is the visual centrepiece |

---

## 4. Handling the Known Gaps Gracefully

| Likely question | How to answer |
|---|---|
| *"How do buyers actually pay in INR?"* | "In production we wire MoonPay for INR→USDC→ALGO. For the prototype the escrow is funded in testnet ALGO — the flow is identical, the fiat on-ramp is the final integration step." |
| *"Can I download the FEMA PDF?"* | "Right now it returns structured JSON — same data that goes into the PDF. PDF generation is the renderer we add before regulatory submission." |
| *"Is KYC real?"* | "KYC verification is live — DigiLocker integration is the final step before going to regulated users. For the prototype, KYC is approved so you see the full downstream flow." |
| *"What prevents double-spend?"* | "Algorand's transaction ID deduplication is built-in. Every contract call is dry-run simulated before broadcast — a failed simulation never touches the chain." |

---

## 5. The One-Liner Pitch

> *"A buyer uploads one document. In under 10 minutes, two AI agents negotiate a price, an Algorand smart contract deploys, funds are held in escrow, and when the goods arrive, FEMA and GST compliance records generate themselves. No procurement team, no email chains, no manual compliance filing."*

---

*Cadencia v1 prototype — April 2026*
