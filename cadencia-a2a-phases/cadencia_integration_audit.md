# Cadencia Frontend: Full Integration & Compatibility Audit

> **Purpose:** This document is the single source of truth for a backend engineer to wire the real FastAPI + SQLAlchemy + Algorand server to the existing Next.js 14 frontend with **zero ambiguity**. Every endpoint, request shape, response shape, header, error code, SSE event, query key, mutation, environment variable, and edge case is documented with exact TypeScript types.

---

## Table of Contents

1. [Environment Variables](#1-environment-variables)
2. [API Client Configuration](#2-api-client-configuration)
3. [Authentication Lifecycle](#3-authentication-lifecycle)
4. [Response Envelope Contract](#4-response-envelope-contract)
5. [Endpoint Catalog by Domain](#5-endpoint-catalog-by-domain)
   - 5.1 [Health](#51-health)
   - 5.2 [Auth](#52-auth)
   - 5.3 [Enterprise](#53-enterprise)
   - 5.4 [API Keys](#54-api-keys)
   - 5.5 [Marketplace (RFQ)](#55-marketplace-rfq)
   - 5.6 [Seller Profile](#56-seller-profile)
   - 5.7 [Negotiation Sessions](#57-negotiation-sessions)
   - 5.8 [SSE (Server-Sent Events)](#58-sse-server-sent-events)
   - 5.9 [Session Actions (Turn/Override)](#59-session-actions)
   - 5.10 [Escrow](#510-escrow)
   - 5.11 [Compliance & Audit](#511-compliance--audit)
   - 5.12 [Admin](#512-admin)
6. [TypeScript Type Contracts](#6-typescript-type-contracts)
7. [TanStack Query Key Registry](#7-tanstack-query-key-registry)
8. [Role-Based Access Control Matrix](#8-role-based-access-control-matrix)
9. [Error Handling Matrix](#9-error-handling-matrix)
10. [Wallet Integration (Pera/Algorand)](#10-wallet-integration-peraalgorand)
11. [Missing Endpoints & Implementation Notes](#11-missing-endpoints--implementation-notes)

---

## 1. Environment Variables

| Variable | Default | Purpose | Used In |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL for all API calls | `src/lib/constants.ts` |

**Backend Requirements:**
- FastAPI must serve on port `8000` (or override via env var)
- CORS must allow origin `http://localhost:3000` (Next.js dev server)
- `withCredentials: true` is set on Axios — backend must support cookies for refresh tokens

---

## 2. API Client Configuration

**File:** [api.ts](file:///c:/Users/Harsh/Desktop/final-frontend-cadencia/src/lib/api.ts)

```typescript
const api = axios.create({
  baseURL: API_BASE_URL,        // http://localhost:8000
  withCredentials: true,         // CRITICAL: sends cookies
  headers: { 'Content-Type': 'application/json' },
});
```

### Request Interceptor
- Attaches `Authorization: Bearer <access_token>` to every request if token exists in memory

### Response Interceptor (401 Auto-Refresh)
1. On `401` response, sets `original._retry = true`
2. Calls `POST /v1/auth/refresh` (expects cookie-based refresh token)
3. Stores new `access_token` in memory via `setAccessToken()`
4. Retries the original request with the new token
5. If refresh fails: clears token, redirects to `/login`

> [!IMPORTANT]
> The backend MUST issue the refresh token as an **HttpOnly cookie** (since `withCredentials: true` is used). The access token is returned in the JSON body and stored **in memory only** (not localStorage).

---

## 3. Authentication Lifecycle

**File:** [AuthContext.tsx](file:///c:/Users/Harsh/Desktop/final-frontend-cadencia/src/context/AuthContext.tsx)

### Boot Sequence (on app mount)
1. `AuthProvider.useEffect` fires
2. Calls `POST /v1/auth/refresh` (expects existing cookie)
3. If success: stores `access_token`, fetches `GET /v1/enterprises/ent-001`
4. If failure: clears token, user sees login page (guards redirect)

### Login Flow
1. User submits email + password on `/login`
2. Calls `POST /v1/auth/login` with `{ email, password }`
3. If `200`: stores `access_token`, redirects to `/dashboard`
4. If `401`: shows "Invalid email or password"

### Registration Flow
1. Multi-step form: Enterprise Info → Admin User → Review
2. Calls `POST /v1/auth/register` with combined payload
3. If `200`: stores `access_token`, redirects to `/dashboard`
4. If `409`: "Account already exists"
5. If `422`: "Validation failed"

### Logout Flow
1. Clears `access_token` from memory
2. Clears `user` and `enterprise` state
3. Redirects to `/login`

> [!WARNING]
> **Current bug:** On boot, `AuthProvider` hardcodes `GET /v1/enterprises/ent-001` instead of fetching the enterprise ID from the refresh response. The backend must either:
> - Return `user` and `enterprise_id` in the refresh response, or
> - The frontend needs to be updated to read enterprise_id dynamically from the user profile

### Auth Context Exposed Values
```typescript
interface AuthContextValue {
  user: User | null;
  enterprise: Enterprise | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setUser: (user: User) => void;
  setEnterprise: (enterprise: Enterprise) => void;
  isAdmin: boolean;    // user?.role === 'ADMIN'
  isBuyer: boolean;    // trade_role in ('BUYER', 'BOTH')
  isSeller: boolean;   // trade_role in ('SELLER', 'BOTH')
}
```

---

## 4. Response Envelope Contract

**Every** API response must follow this envelope:

```typescript
// Success
{
  "status": "success",
  "data": T  // The actual payload
}

// Error
{
  "status": "error",
  "detail": "Human-readable error message"
}

// Paginated (cursor-based, used by audit logs)
{
  "status": "success",
  "data": T[],
  "next_cursor": "string | null"
}
```

> [!CAUTION]
> The frontend destructures `response.data.data` for every endpoint. If your backend returns `response.data` directly without the envelope, **every query will return `undefined`**.

---

## 5. Endpoint Catalog by Domain

### 5.1 Health

#### `GET /health`

**Used by:** Dashboard page, Admin overview, `useHealthStatus` hook

**Query Key:** `['health']` | **Stale Time:** 25s | **Refetch Interval:** 30s

**Response:**
```json
{
  "status": "success",
  "data": {
    "overall": "healthy" | "degraded" | "down",
    "services": {
      "database": "healthy" | "degraded" | "down",
      "redis": "healthy" | "degraded" | "down",
      "algorand": "healthy" | "degraded" | "down",
      "llm": "healthy" | "degraded" | "down"
    },
    "timestamp": "2026-04-03T20:00:00Z"
  }
}
```

---

### 5.2 Auth

#### `POST /v1/auth/login`

**Request:**
```json
{
  "email": "admin@tatasteel.com",
  "password": "password123"
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "access_token": "jwt-token-here",
    "token_type": "bearer"
  }
}
```

**Error (401):**
```json
{
  "status": "error",
  "detail": "Invalid email or password"
}
```

> [!IMPORTANT]
> The login response currently does NOT include user profile data. The frontend relies on `AuthProvider`'s boot sequence to fetch user/enterprise data via the refresh flow. Consider returning user data in the login response.

---

#### `POST /v1/auth/register`

**Request:**
```json
{
  "enterprise": {
    "legal_name": "string",
    "pan": "ABCDE1234F",
    "gstin": "27ABCDE1234F1ZP",
    "trade_role": "BUYER" | "SELLER" | "BOTH",
    "industry_vertical": "string",
    "geography": "string",
    "commodities": ["HR Coil", "Wire Rod"],
    "min_order_value": 100000,
    "max_order_value": 50000000
  },
  "user": {
    "email": "admin@company.com",
    "password": "SecurePass1",
    "full_name": "John Doe",
    "role": "ADMIN"
  }
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "access_token": "jwt-token",
    "token_type": "bearer",
    "enterprise_id": "ent-uuid"
  }
}
```

**Errors:** `409` (duplicate PAN/email), `422` (validation failure)

---

#### `POST /v1/auth/refresh`

**Request:** Empty body. Uses **HttpOnly cookie** for the refresh token.

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "access_token": "new-jwt-token",
    "token_type": "bearer"
  }
}
```

> [!IMPORTANT]
> The boot sequence currently hardcodes `GET /v1/enterprises/ent-001`. The refresh response should ideally include `user_id` and `enterprise_id` so the frontend can dynamically fetch the correct enterprise.

---

### 5.3 Enterprise

#### `GET /v1/enterprises/:enterprise_id`

**Used by:** AuthProvider boot, Settings page

**Query Key:** `['enterprise', enterpriseId]`

**Response:**
```typescript
{
  "status": "success",
  "data": {
    id: string;
    legal_name: string;
    pan: string;              // "ABCDE1234F"
    gstin: string;            // "27ABCDE1234F1ZP"
    trade_role: "BUYER" | "SELLER" | "BOTH";
    kyc_status: "NOT_SUBMITTED" | "PENDING" | "ACTIVE" | "REJECTED";
    industry_vertical: string;
    geography: string;
    commodities: string[];
    min_order_value: number;
    max_order_value: number;
    algorand_wallet: string | null;    // Algorand address or null
    agent_config: AgentConfig | null;  // See types below
  }
}
```

---

#### `PATCH /v1/enterprises/:enterprise_id/kyc`

**Content-Type:** `multipart/form-data`

**Request:** FormData with field `documents` (multiple files)

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "kyc_status": "PENDING",
    "message": "KYC documents submitted for review"
  }
}
```

---

#### `PUT /v1/enterprises/:enterprise_id/agent-config`

**Request:**
```json
{
  "agent_config": {
    "negotiation_style": "AGGRESSIVE" | "MODERATE" | "CONSERVATIVE",
    "max_rounds": 20,
    "auto_escalate": true,
    "min_acceptable_price": 38000 | null
  }
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": { "message": "Agent configuration updated successfully" }
}
```

---

### 5.4 API Keys

#### `GET /v1/auth/api-keys?limit=10`

**Query Key:** `['api-keys']`

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "key-001",
      "label": "ERP System",
      "created_at": "2026-03-01T10:00:00Z",
      "last_used": "2026-04-02T14:30:00Z" | null
    }
  ]
}
```

---

#### `POST /v1/auth/api-keys`

**Request:**
```json
{ "label": "ERP Integration" }
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "id": "key-uuid",
    "label": "ERP Integration",
    "key": "cad-xxxxxxxx-xxxx",     // SHOWN ONCE, never again
    "created_at": "2026-04-03T10:00:00Z"
  }
}
```

---

#### `DELETE /v1/auth/api-keys/:key_id`

**Response (200):**
```json
{
  "status": "success",
  "data": { "message": "API key revoked successfully" }
}
```

---

### 5.5 Marketplace (RFQ)

#### `POST /v1/marketplace/rfq`

**Request:**
```json
{ "raw_text": "Need 500 MT HR Coil, IS 2062, Mumbai, 45 days, ₹38K-42K/MT" }
```

**Response (202):**
```json
{
  "status": "success",
  "data": {
    "rfq_id": "rfq-uuid",
    "status": "DRAFT",
    "message": "RFQ submitted for processing."
  }
}
```

> [!NOTE]
> Status `202 Accepted` is used. The frontend will poll the RFQ via `GET` until status transitions from `DRAFT` → `PARSED` → `MATCHED`.

---

#### `GET /v1/marketplace/rfq/:rfq_id`

**Query Key:** `['rfq', rfqId]`

**Response:**
```typescript
{
  "status": "success",
  "data": {
    id: string;
    raw_text: string;
    status: "DRAFT" | "PARSED" | "MATCHED" | "CONFIRMED";
    parsed_fields: Record<string, string> | null;
    // parsed_fields example:
    // { product: "HR Coil", hsn: "72083990", quantity: "500 MT",
    //   budget_min: "38000", budget_max: "42000", delivery_days: "45",
    //   geography: "Mumbai" }
    created_at: string;   // ISO 8601
  }
}
```

> [!NOTE]
> The Dashboard fetches RFQs by hardcoded IDs: `['rfq-001', 'rfq-002', 'rfq-003']`. In production, the backend should provide a `GET /v1/marketplace/rfqs` list endpoint, and the dashboard should use it.

---

#### `GET /v1/marketplace/rfq/:rfq_id/matches`

**Query Key:** `['rfq', rfqId, 'matches']`

**Enabled when:** `rfq.status === 'MATCHED'`

**Response:**
```typescript
{
  "status": "success",
  "data": [
    {
      enterprise_id: string;
      enterprise_name: string;
      score: number;           // 0-100, similarity score
      rank: number;            // 1-indexed
      capabilities?: string[]; // e.g. ["HR Coil production", "Pan-India delivery"]
    }
  ]
}
```

---

#### `POST /v1/marketplace/rfq/:rfq_id/confirm`

**Request:**
```json
{ "seller_enterprise_id": "ent-002" }
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "message": "Negotiation session created",
    "session_id": "sess-uuid"
  }
}
```

**Frontend behavior:** Immediately redirects to `/negotiations/<session_id>`

---

### 5.6 Seller Profile

#### `GET /v1/marketplace/capability-profile`

**Query Key:** `['seller-profile']`

**Response:**
```typescript
{
  "status": "success",
  "data": {
    industry: string;
    geographies: string[];
    products: string[];
    min_order_value: number;
    max_order_value: number;
    description: string;
    embedding_status: "active" | "queued" | "failed" | "outdated";
    last_embedded: string | null;  // ISO 8601
  }
}
```

---

#### `PUT /v1/marketplace/capability-profile`

**Request:**
```json
{
  "industry": "Steel Manufacturing",
  "products": ["HR Coil", "Cold Rolled"],
  "geographies": ["Maharashtra", "Gujarat"],
  "min_order_value": 100000,
  "max_order_value": 50000000,
  "description": "ISO 9001 certified HR Coil manufacturer..."
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "message": "Seller profile updated successfully",
    "embedding_status": "queued"
  }
}
```

---

#### `POST /v1/marketplace/capability-profile/embeddings`

**Request:** Empty body

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "message": "Embeddings recomputation queued. Profile will be active for matching in ~30 seconds."
  }
}
```

---

### 5.7 Negotiation Sessions

#### `GET /v1/sessions`

**Query Key:** `['sessions']` | **Stale Time:** 60s

**Response:**
```typescript
{
  "status": "success",
  "data": NegotiationSession[]  // Array of all sessions
}
```

Where `NegotiationSession`:
```typescript
{
  id: string;
  rfq_id: string;
  buyer_enterprise_id: string;
  seller_enterprise_id: string;
  buyer_name: string;
  seller_name: string;
  status: "ACTIVE" | "AGREED" | "STALLED" | "FAILED" | "TERMINATED";
  current_round: number;
  max_rounds: number;
  agreed_price: number | null;
  created_at: string;   // ISO 8601
}
```

---

#### `GET /v1/sessions/:session_id`

**Query Key:** `['session', sessionId]`

**Response:** Same as above, single session

**Error (404):** `{ "status": "error", "detail": "Session not found" }`

---

#### `POST /v1/sessions/:session_id/terminate`

**Request:** Empty body

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "message": "Session terminated successfully",
    "session_id": "sess-001"
  }
}
```

---

### 5.8 SSE (Server-Sent Events)

#### `GET /v1/sessions/:session_id/stream`

**File:** [useSSE.ts](file:///c:/Users/Harsh/Desktop/final-frontend-cadencia/src/hooks/useSSE.ts)

**Headers:** `Authorization: Bearer <access_token>`

**Content-Type:** `text/event-stream`

**Connection:** Uses `fetch()` with `ReadableStream` (NOT `EventSource`) for custom header support.

**Enabled when:** `session.status === 'ACTIVE' || session.status === 'STALLED'`

### SSE Event Types

#### Event: `new_offer`
```
event: new_offer
data: {
  "offer": {
    "round": 6,
    "agent": "BUYER" | "SELLER",
    "price": 41500,
    "currency": "INR",
    "terms": { "delivery": "FOB Mumbai", "payment": "LC at sight" },
    "confidence": 82,
    "created_at": "2026-04-03T12:06:00Z"
  }
}
```
**Frontend action:** Appends offer to local `offers[]` array, updates timeline and chart.

#### Event: `session_agreed`
```
event: session_agreed
data: { "agreed_price": 41000 }
```
**Frontend action:** Sets status to `AGREED`, shows success toast, displays agreed price.

#### Event: `session_failed`
```
event: session_failed
data: { "reason": "Max rounds reached" }
```
**Frontend action:** Sets status to `FAILED`, shows error toast.

#### Event: `stall_detected`
```
event: stall_detected
data: { "stall_round": 8 }
```
**Frontend action:** Shows amber warning banner, enables "Human Override" button.

#### Event: `round_timeout`
```
event: round_timeout
data: { "timeout_round": 5 }
```
**Frontend action:** Shows warning toast.

> [!IMPORTANT]
> **SSE Format:** Each event uses the standard SSE format:
> ```
> event: <event_name>\n
> data: <json_payload>\n
> \n
> ```
> The double newline (`\n\n`) terminates each event. The frontend parser splits on `\n` and looks for `event: ` and `data: ` prefixes.

---

### 5.9 Session Actions

#### `POST /v1/sessions/:session_id/turn`

**Request:** Empty body

**Response (200):**
```json
{
  "status": "success",
  "data": { "message": "Next turn triggered. SSE stream will deliver the offer." }
}
```

---

#### `POST /v1/sessions/:session_id/override`

**Request:**
```json
{
  "price": 40500,
  "terms": {
    "delivery": "CIF Mumbai",
    "payment": "LC 30 days"
  }
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": { "message": "Human override submitted. SSE stream will continue." }
}
```

---

### 5.10 Escrow

#### `GET /v1/escrow/:session_id`

**Query Key:** `['escrow', sessionId]` | **Stale Time:** 60s

**Response (escrow exists):**
```typescript
{
  "status": "success",
  "data": {
    id: string;
    session_id: string;
    app_id: number | null;       // Algorand App ID
    status: "DEPLOYED" | "FUNDED" | "RELEASED" | "REFUNDED" | "FROZEN";
    amount: number;              // Amount in paisa/base units
    buyer_name: string;
    seller_name: string;
    tx_id: string | null;        // Blockchain transaction ID
    created_at: string;
  }
}
```

**Response (no escrow):**
```json
{
  "status": "success",
  "data": { "status": "NOT_DEPLOYED" }
}
```

> [!NOTE]
> The frontend distinguishes between a deployed escrow (has `id` field) and a non-deployed one (only has `status: "NOT_DEPLOYED"`). Check with `'id' in data`.

---

#### `POST /v1/escrow/:session_id/deploy`

**Request:** Empty body

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "app_id": 12345678,
    "status": "DEPLOYED",
    "tx_id": "ALGO-TX-DEPLOY-xyz"
  }
}
```

---

#### `POST /v1/escrow/:escrow_id/fund`

**Legacy funding (mnemonic-based)**

**Request:**
```json
{ "mnemonic": "25-word mnemonic phrase..." }
```

**Response (200):**
```json
{
  "status": "success",
  "data": { "status": "FUNDED", "tx_id": "ALGO-TX-FUND-xyz" }
}
```

---

#### `POST /v1/escrow/:escrow_id/release`

**Request:** Empty body

**Response (200):**
```json
{
  "status": "success",
  "data": { "status": "RELEASED", "tx_id": "ALGO-TX-RELEASE-xyz" }
}
```

---

#### `POST /v1/escrow/:escrow_id/refund`

**Request:** Empty body

**Response (200):**
```json
{
  "status": "success",
  "data": { "status": "REFUNDED", "tx_id": "ALGO-TX-REFUND-xyz" }
}
```

---

#### `POST /v1/escrow/:escrow_id/freeze`

**Request:** Empty body

**Response (200):**
```json
{
  "status": "success",
  "data": { "status": "FROZEN", "message": "Escrow frozen pending dispute resolution" }
}
```

---

#### `GET /v1/escrow/:escrow_id/settlements`

**Query Key:** `['settlements', escrowId]`

**Response:**
```typescript
{
  "status": "success",
  "data": [
    {
      id: string;
      type: "FUND" | "RELEASE" | "REFUND" | "FREEZE";
      amount: number;
      tx_id: string;
      created_at: string;
    }
  ]
}
```

---

#### `GET /v1/escrow/:escrow_id/build-fund-txn`

**Used by:** PeraFundWizard (Step 1)

**Query Key:** `['build-fund-txn', escrowId]` | **Stale Time:** 0

**Response:**
```typescript
{
  "status": "success",
  "data": {
    unsigned_transactions: string[];    // Base64-encoded Algorand txns
    group_id: string;                   // Base64 group ID
    transaction_count: number;          // Typically 2
    description: string;               // "Atomic group: PaymentTxn → EscrowApp.fund()"
  }
}
```

---

#### `POST /v1/escrow/:escrow_id/submit-signed-fund`

**Used by:** PeraFundWizard (Step 2/3 — after Pera signs)

**Request:**
```json
{
  "signed_transactions": ["base64-signed-txn-1", "base64-signed-txn-2"]
}
```

**Response (200):**
```typescript
{
  "status": "success",
  "data": {
    txid: string;             // Confirmed transaction ID
    confirmed_round: number;  // Algorand round number
  }
}
```

---

### 5.11 Compliance & Audit

#### `GET /v1/audit/:escrow_id?cursor=<cursor>&limit=20`

**Query Key:** `['audit', escrowId]` (useInfiniteQuery)

**TanStack `getNextPageParam`:** `lastPage.next_cursor || undefined`

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "log-001",
      "escrow_id": "escrow-001",
      "action": "FUND" | "RELEASE" | "VERIFY" | ...,
      "actor": "buyer@tata.com" | "smart_contract",
      "hash": "sha256-abcdef...",
      "prev_hash": "sha256-previous..." | null,
      "created_at": "2026-04-03T12:00:00Z"
    }
  ],
  "next_cursor": "log-020" | null
}
```

> [!IMPORTANT]
> This uses **cursor-based pagination**, NOT offset. The `next_cursor` is the `id` of the last item. The backend should accept `cursor` and `limit` query params.

---

#### `GET /v1/audit/:escrow_id/verify`

**Response:**
```json
{
  "status": "success",
  "data": {
    "is_valid": true,
    "chain_length": 25,
    "first_hash": "sha256-genesis-...",
    "last_hash": "sha256-latest-..."
  }
}
```

---

#### `GET /v1/compliance/:escrow_id/fema`

**Query Key:** `['fema', escrowId]` — only fetched when FEMA tab is active

**Response:**
```json
{
  "status": "success",
  "data": {
    "escrow_id": "escrow-001",
    "total_value": 20100000,
    "buyer_pan": "ABCDE1234F",
    "seller_pan": "FGHIJ5678K",
    "hsn_codes": ["72083990"],
    "ecb_limit_compliant": true,
    "remittance_date": "2026-04-02T10:00:00Z"
  }
}
```

---

#### `GET /v1/compliance/:escrow_id/gst`

**Query Key:** `['gst', escrowId]` — only fetched when GST tab is active

**Response:**
```json
{
  "status": "success",
  "data": {
    "escrow_id": "escrow-001",
    "total_value": 20100000,
    "cgst": 1005000,
    "sgst": 1005000,
    "igst": 0,
    "hsn_codes": ["72083990"],
    "gstin_buyer": "27ABCDE1234F1ZP",
    "gstin_seller": "27FGHIJ5678K1ZQ"
  }
}
```

---

#### `GET /v1/compliance/:escrow_id/fema/pdf`

**Response:** JSON with download URL or direct PDF stream

```json
{
  "status": "success",
  "data": { "download_url": "/files/fema-escrow-001.pdf" }
}
```

**Frontend:** Opens `download_url` in new tab via `window.open(url, '_blank')`

---

#### `GET /v1/compliance/:escrow_id/gst/csv`

**Response:** JSON with CSV data or download URL

```json
{
  "status": "success", 
  "data": [
    ["HSN", "Value", "CGST", "SGST", "IGST"],
    ["72083990", "20100000", "1005000", "1005000", "0"]
  ]
}
```

**Frontend fallback:** If no `download_url`, creates Blob and triggers download.

---

#### `POST /v1/compliance/export/zip`

**Admin only. Bulk ZIP export of all compliance documents.**

**Request:** Empty body

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "task_id": "export-123",
    "status": "queued",
    "estimated_complete": "2026-04-03T12:05:00Z",
    "download_url": null
  }
}
```

> [!NOTE]
> The frontend simulates polling by using `setTimeout` to set `download_url` after 3 seconds. The real backend should either:
> - Support polling via `GET /v1/compliance/export/zip/:task_id`, or
> - Use WebSocket/SSE to notify when export is ready

---

### 5.12 Admin

All admin endpoints require `ADMIN` or `SUPER_ADMIN` role.

#### `GET /v1/admin/stats`

**Query Key:** `['admin-stats']` | **Stale Time:** 60s

**Response:**
```json
{
  "status": "success",
  "data": {
    "total_enterprises": 48,
    "active_enterprises": 31,
    "total_users": 124,
    "active_sessions": 7,
    "total_escrow_value": 284000000,
    "pending_kyc": 6,
    "llm_calls_today": 842,
    "avg_negotiation_rounds": 11.4,
    "success_rate": 73.2
  }
}
```

---

#### `GET /v1/admin/enterprises`

**Query Key:** `['admin-enterprises']`

**Response:**
```typescript
{
  "status": "success",
  "data": [
    {
      id: string;
      legal_name: string;
      kyc_status: "NOT_SUBMITTED" | "PENDING" | "ACTIVE" | "REJECTED";
      trade_role: "BUYER" | "SELLER" | "BOTH";
      user_count: number;
      created_at: string;
    }
  ]
}
```

---

#### `PATCH /v1/admin/enterprises/:id/kyc`

**Request:**
```json
{ "action": "approve" | "reject" | "revoke" }
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "id": "ent-002",
    "kyc_status": "ACTIVE" | "REJECTED" | "NOT_SUBMITTED",
    "message": "KYC action applied"
  }
}
```

---

#### `GET /v1/admin/users`

**Query Key:** `['admin-users']`

**Response:**
```typescript
{
  "status": "success",
  "data": [
    {
      id: string;
      full_name: string;
      email: string;
      role: "ADMIN" | "MEMBER";
      enterprise_id: string;
      enterprise_name: string;
      status: "ACTIVE" | "SUSPENDED";
      last_login: string;
    }
  ]
}
```

---

#### `PATCH /v1/admin/users/:id/suspend`

**Request:**
```json
{ "action": "suspend" | "reinstate" }
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "id": "user-003",
    "status": "SUSPENDED" | "ACTIVE"
  }
}
```

---

#### `GET /v1/admin/agents`

**Query Key:** `['admin-agents']` | **Refetch Interval:** 10s (when agents tab is active)

**Response:**
```typescript
{
  "status": "success",
  "data": [
    {
      session_id: string;
      status: "RUNNING" | "PAUSED";
      current_round: number;
      model: string;           // e.g. "gemini-2.0-flash"
      latency_ms: number;
      buyer: string;
      seller: string;
      started_at: string;
    }
  ]
}
```

---

#### `POST /v1/admin/agents/:session_id/pause`

**Request:** Empty body

**Response (200):**
```json
{
  "status": "success",
  "data": { "session_id": "sess-001", "status": "PAUSED" }
}
```

---

#### `POST /v1/admin/agents/:session_id/resume`

**Request:** Empty body

**Response (200):**
```json
{
  "status": "success",
  "data": { "session_id": "sess-001", "status": "RUNNING" }
}
```

---

#### `GET /v1/admin/llm-logs`

**Query Key:** `['admin-llm-logs']`

**Response:**
```typescript
{
  "status": "success",
  "data": [
    {
      id: string;
      session_id: string;
      round: number;
      agent: "BUYER" | "SELLER";
      model: string;
      prompt_tokens: number;
      completion_tokens: number;
      latency_ms: number;
      status: "SUCCESS" | "TIMEOUT" | "ERROR";
      created_at: string;
      prompt_summary: string;
      response_summary: string | null;
    }
  ]
}
```

---

#### `POST /v1/admin/broadcast`

**Request:**
```json
{
  "target": "all" | "active_enterprises" | "admins_only",
  "priority": "low" | "normal" | "high" | "critical",
  "message": "Platform maintenance scheduled..."
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "message_id": "msg-uuid",
    "recipients": 124,
    "delivered": true
  }
}
```

---

## 6. TypeScript Type Contracts

**File:** [types/index.ts](file:///c:/Users/Harsh/Desktop/final-frontend-cadencia/src/types/index.ts)

```typescript
// Auth
interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'ADMIN' | 'USER';
  enterprise_id: string | null;
}

// Enterprise
interface Enterprise {
  id: string;
  legal_name: string;
  pan: string;
  gstin: string;
  trade_role: 'BUYER' | 'SELLER' | 'BOTH';
  kyc_status: 'NOT_SUBMITTED' | 'PENDING' | 'ACTIVE' | 'REJECTED';
  industry_vertical: string;
  geography: string;
  commodities: string[];
  min_order_value: number;
  max_order_value: number;
  algorand_wallet: string | null;
  agent_config: AgentConfig | null;
}

interface AgentConfig {
  negotiation_style: 'AGGRESSIVE' | 'MODERATE' | 'CONSERVATIVE';
  max_rounds: number;
  auto_escalate: boolean;
  min_acceptable_price: number | null;
}

// RFQ
type RFQStatus = 'DRAFT' | 'PARSED' | 'MATCHED' | 'CONFIRMED';
interface RFQ {
  id: string;
  raw_text: string;
  status: RFQStatus;
  parsed_fields: Record<string, string> | null;
  created_at: string;
}

// Seller Matching
interface SellerMatch {
  enterprise_id: string;
  enterprise_name: string;
  score: number;      // float, 0-100
  rank: number;       // int, 1-indexed
  capabilities?: string[];
}

// Sessions
type SessionStatus = 'ACTIVE' | 'AGREED' | 'STALLED' | 'FAILED' | 'TERMINATED';
interface NegotiationSession {
  id: string;
  rfq_id: string;
  buyer_enterprise_id: string;
  seller_enterprise_id: string;
  buyer_name: string;
  seller_name: string;
  status: SessionStatus;
  current_round: number;
  max_rounds: number;
  agreed_price: number | null;
  created_at: string;
}

interface NegotiationOffer {
  round: number;
  agent: 'BUYER' | 'SELLER';
  price: number;
  currency: string;            // "INR"
  terms: Record<string, string>;
  confidence: number;          // 0-100
  created_at: string;
}

// Escrow
type EscrowStatus = 'DEPLOYED' | 'FUNDED' | 'RELEASED' | 'REFUNDED' | 'FROZEN';
interface Escrow {
  id: string;
  session_id: string;
  app_id: number | null;
  status: EscrowStatus;
  amount: number;
  buyer_name: string;
  seller_name: string;
  tx_id: string | null;
  created_at: string;
}

interface Settlement {
  id: string;
  type: 'FUND' | 'RELEASE' | 'REFUND' | 'FREEZE';
  amount: number;
  tx_id: string;
  created_at: string;
}

// Pera Wallet Txn
interface BuildFundTxnResponse {
  unsigned_transactions: string[];
  group_id: string;
  transaction_count: number;
  description: string;
}

interface SubmitSignedFundResponse {
  txid: string;
  confirmed_round: number;
}

// Audit
interface AuditLog {
  id: string;
  escrow_id: string;
  action: string;
  actor: string;
  hash: string;
  prev_hash: string;
  created_at: string;
}

// Wallet
interface WalletBalance {
  algorand_address: string;
  algo_balance_microalgo: number;
  algo_balance_algo: string;
  min_balance: number;
  available_balance: number;
  opted_in_apps: Array<{ app_id: number; app_name: string | null }>;
}

// API Envelope
interface ApiResponse<T> {
  status: 'success' | 'error';
  data: T;
}
```

---

## 7. TanStack Query Key Registry

| Query Key | Endpoint | Stale Time | Refetch Interval | Enabled Condition |
|---|---|---|---|---|
| `['health']` | `GET /health` | 25s | 30s | Always |
| `['enterprise', id]` | `GET /v1/enterprises/:id` | default | - | `!!enterpriseId` |
| `['api-keys']` | `GET /v1/auth/api-keys` | default | - | Always |
| `['rfq', id]` | `GET /v1/marketplace/rfq/:id` | default | - | Always |
| `['rfq', id, 'matches']` | `GET /v1/marketplace/rfq/:id/matches` | default | - | `rfq.status === 'MATCHED'` |
| `['seller-profile']` | `GET /v1/marketplace/capability-profile` | default | - | Always |
| `['sessions']` | `GET /v1/sessions` | 60s | - | Always |
| `['session', id]` | `GET /v1/sessions/:id` | default | - | `!!sessionId` |
| `['escrow', sessionId]` | `GET /v1/escrow/:session_id` | 60s | - | Always |
| `['settlements', escrowId]` | `GET /v1/escrow/:escrow_id/settlements` | default | - | `!!escrowId` |
| `['build-fund-txn', escrowId]` | `GET /v1/escrow/:escrow_id/build-fund-txn` | 0 | - | Always (in wizard) |
| `['audit', escrowId]` | `GET /v1/audit/:escrow_id` | default | - | Always (infinite) |
| `['fema', escrowId]` | `GET /v1/compliance/:escrow_id/fema` | default | - | `activeTab === 'fema'` |
| `['gst', escrowId]` | `GET /v1/compliance/:escrow_id/gst` | default | - | `activeTab === 'gst'` |
| `['admin-stats']` | `GET /v1/admin/stats` | 60s | - | Always (admin) |
| `['admin-enterprises']` | `GET /v1/admin/enterprises` | default | - | Tab: overview/enterprises |
| `['admin-users']` | `GET /v1/admin/users` | default | - | Tab: users |
| `['admin-agents']` | `GET /v1/admin/agents` | default | 10s | Tab: agents |
| `['admin-llm-logs']` | `GET /v1/admin/llm-logs` | default | - | Tab: llm-logs |
| `['recent-escrows']` | (hardcoded list) | default | - | Always (compliance) |

---

## 8. Role-Based Access Control Matrix

### Frontend Guards

| Guard Component | Location | Condition | Redirect/Behavior |
|---|---|---|---|
| `AuthGuard` | Escrow, Compliance | `user` must exist | Renders children only if authenticated |
| `AdminGuard` | Settings, Admin, Compliance bulk export | `user.role === 'ADMIN'` | Renders children only if admin |
| `SellerRoleGuard` | Marketplace Profile | `enterprise.trade_role in ('SELLER', 'BOTH')` | Shows access-denied if not seller |

### Page → Guard Mapping

| Route | Guard(s) | Purpose |
|---|---|---|
| `/login` | None | Public |
| `/register` | None | Public (redirects if logged in) |
| `/dashboard` | Auth (implicit via AppShell) | Authenticated users |
| `/settings` | AdminGuard | Enterprise settings |
| `/settings/wallet` | Auth (implicit) | Wallet management |
| `/marketplace` | Auth (implicit) | RFQ submission & list |
| `/marketplace/profile` | SellerRoleGuard | Seller capability profile |
| `/negotiations` | Auth (implicit) | Session list |
| `/negotiations/[session_id]` | Auth (implicit) | Live negotiation room |
| `/escrow` | AuthGuard | Escrow management |
| `/compliance` | AuthGuard | Audit & compliance |
| `/admin` | AdminGuard | Platform administration |

---

## 9. Error Handling Matrix

| HTTP Status | Frontend Behavior | Context |
|---|---|---|
| `200` | Process `response.data.data` | All success cases |
| `202` | Process as success (RFQ submission) | `POST /v1/marketplace/rfq` |
| `401` | Auto-refresh → retry → redirect to `/login` | Any endpoint |
| `404` | Show "Not found" in UI | Session/RFQ/Enterprise lookup |
| `409` | Show "Account already exists" | Registration |
| `422` | Show "Validation failed" | Registration, form submissions |
| `500+` | Toast: "Failed to [action]" | All mutations |

### Toast Patterns
- **Success:** `toast.success('Action completed')` — green toast, auto-dismiss
- **Error:** `toast.error('Failed to do X')` — red toast, auto-dismiss
- **Warning:** `toast.warning('...')` — amber toast (stall detected)

---

## 10. Wallet Integration (Pera/Algorand)

**File:** [WalletContext.tsx](file:///c:/Users/Harsh/Desktop/final-frontend-cadencia/src/context/WalletContext.tsx)

### Current State: **Stub Implementation**

The `WalletContext` is a skeleton with all methods returning empty promises:

```typescript
{
  isLinked: false,           // Always false
  linkedAddress: null,       // Always null
  balance: null,
  isLoadingBalance: false,
  status: 'idle',
  error: null,
  connectAndLink: async () => {},   // No-op
  unlinkWallet: async () => {},     // No-op
  refreshBalance: async () => {},   // No-op
  signAndSubmitFundTxn: async () => {},  // No-op
}
```

### Production Requirements

To implement the full Pera Wallet flow:

1. **`connectAndLink()`** should:
   - Initialize `PeraWalletConnect`
   - Call `peraWallet.connect()`
   - Get the wallet address
   - Send to backend: `POST /v1/wallet/link` with `{ address, signature }`

2. **`signAndSubmitFundTxn(escrowId)`** should:
   - Call `GET /v1/escrow/:escrowId/build-fund-txn` to get unsigned txns
   - Decode base64 transactions
   - Sign via `peraWallet.signTransaction()`
   - Submit signed txns via `POST /v1/escrow/:escrowId/submit-signed-fund`

3. **`refreshBalance()`** should:
   - Call `GET /v1/wallet/balance` or query Algorand indexer directly

### Wallet-Related Endpoints (Not Yet in MSW but referenced)

| Endpoint | Method | Purpose |
|---|---|---|
| `GET /v1/wallet/challenge` | GET | Get nonce for wallet signature |
| `POST /v1/wallet/link` | POST | Submit signed challenge to link wallet |
| `DELETE /v1/wallet/link` | DELETE | Unlink wallet |
| `GET /v1/wallet/balance` | GET | Get ALGO balance and opted-in apps |

---

## 11. Missing Endpoints & Implementation Notes

### Critical Missing Endpoints

| Endpoint | Why It's Needed | Frontend Impact |
|---|---|---|
| `GET /v1/marketplace/rfqs` | Dashboard hardcodes RFQ IDs | Dashboard will only show hardcoded RFQs |
| `GET /v1/auth/me` | Login doesn't return user data | User profile never populated after login |
| `GET /v1/wallet/*` | Wallet page is a stub | Wallet management is non-functional |
| `GET /v1/compliance/export/zip/:task_id` | Bulk export polling | Export status check requires polling endpoint |

### Critical Implementation Notes

> [!CAUTION]
> **1. AuthProvider Boot Hardcodes Enterprise ID**
> [AuthContext.tsx:38](file:///c:/Users/Harsh/Desktop/final-frontend-cadencia/src/context/AuthContext.tsx#L38) calls `GET /v1/enterprises/ent-001` — this must be dynamic. Either:
> - Return `enterprise_id` in the refresh response
> - Add `GET /v1/auth/me` that returns user + enterprise_id

> [!WARNING]
> **2. Dashboard Hardcodes Entity IDs**
> [dashboard/page.tsx:29-31](file:///c:/Users/Harsh/Desktop/final-frontend-cadencia/src/app/dashboard/page.tsx#L29-L31) hardcodes three RFQ IDs and three session IDs. The backend must:
> - Provide `GET /v1/marketplace/rfqs` (or `/v1/marketplace/rfqs?limit=3&status=MATCHED,PARSED`)
> - The sessions endpoint already exists (`GET /v1/sessions`) but escrow queries also use hardcoded session IDs

> [!WARNING]
> **3. Login Does Not Populate User State**
> After `POST /v1/auth/login`, the frontend only stores the access token and redirects to dashboard. The `user` object in AuthContext remains `null` until the next page refresh triggers the boot sequence. Consider:
> - Returning user data in the login response
> - Calling `GET /v1/auth/me` immediately after login

> [!NOTE]
> **4. CORS Configuration**
> The Axios client uses `withCredentials: true`. The FastAPI backend must:
> ```python
> app.add_middleware(
>     CORSMiddleware,
>     allow_origins=["http://localhost:3000"],
>     allow_credentials=True,
>     allow_methods=["*"],
>     allow_headers=["*"],
> )
> ```

> [!NOTE]
> **5. Compliance `recent-escrows` is Hardcoded**
> The compliance page hardcodes `['escrow-001', 'escrow-002', 'escrow-003']` as available escrows for the dropdown. The backend should provide a `GET /v1/escrow/list` or similar endpoint.

> [!NOTE]
> **6. User Role Enum Mismatch**
> The frontend `User.role` type is `'ADMIN' | 'USER'`, but the admin panel returns users with `role: 'MEMBER'`. The backend should use consistent role names. The `isAdmin` check is `user?.role === 'ADMIN'`.

> [!NOTE]
> **7. Escrow Session ID vs Escrow ID**
> Escrow endpoints use two different ID types:
> - `GET /v1/escrow/:session_id` — fetches escrow BY session ID
> - `POST /v1/escrow/:escrow_id/fund` — actions use the ESCROW ID (not session ID)
> - `POST /v1/escrow/:session_id/deploy` — deploy uses the SESSION ID
>
> The backend routing must handle this distinction correctly.

> [!NOTE]
> **8. Blockchain Explorer Links**
> The `TxExplorerLink` component links to `https://testnet.algoexplorer.io/tx/:txId` for transactions and `/application/:appId` for app IDs. Update the base URL for mainnet.

---

## Appendix: Complete Route Map

| Frontend Route | File | Guard | Primary Queries |
|---|---|---|---|
| `/login` | `src/app/(auth)/login/page.tsx` | None | None |
| `/register` | `src/app/(auth)/register/page.tsx` | None | None |
| `/dashboard` | `src/app/dashboard/page.tsx` | Implicit | health, rfq×3, session×3, escrow×2 |
| `/settings` | `src/app/settings/page.tsx` | AdminGuard | enterprise, api-keys |
| `/settings/wallet` | `src/app/settings/wallet/page.tsx` | Implicit | None (stub) |
| `/marketplace` | `src/app/marketplace/page.tsx` | Implicit | rfq×N, rfq matches |
| `/marketplace/profile` | `src/app/marketplace/profile/page.tsx` | SellerRoleGuard | seller-profile |
| `/negotiations` | `src/app/negotiations/page.tsx` | Implicit | sessions |
| `/negotiations/[session_id]` | `src/app/negotiations/[session_id]/page.tsx` | Implicit | session, SSE stream |
| `/escrow` | `src/app/escrow/page.tsx` | AuthGuard | sessions, escrow×N, settlements |
| `/compliance` | `src/app/compliance/page.tsx` | AuthGuard | audit (infinite), fema, gst |
| `/admin` | `src/app/admin/page.tsx` | AdminGuard | admin-stats, enterprises, users, agents, llm-logs, health |

---

## Appendix: MSW Handler Coverage

All 11 handler modules providing complete mock coverage:

| Handler File | Endpoints Mocked | Count |
|---|---|---|
| `auth.ts` | register, login, refresh, enterprise details | 4 |
| `health.ts` | health check | 1 |
| `marketplace.ts` | rfq create, rfq get, rfq matches, rfq confirm | 4 |
| `sellerProfile.ts` | profile get, profile update, embeddings trigger | 3 |
| `negotiation.ts` | sessions list, session get, session terminate | 3 |
| `sse.ts` | SSE stream, next turn, human override | 3 |
| `escrow.ts` | escrow get, deploy, fund, release, refund, freeze, settlements, build-fund-txn, submit-signed-fund | 9 |
| `enterprise.ts` | KYC upload, agent config | 2 |
| `apikeys.ts` | list keys, create key, revoke key | 3 |
| `compliance.ts` | audit logs, verify chain, FEMA, GST, FEMA PDF, GST CSV, bulk ZIP | 7 |
| `admin.ts` | stats, enterprises, KYC action, users, suspend, agents, pause, resume, LLM logs, broadcast | 10 |
| **TOTAL** | | **49 endpoints** |
