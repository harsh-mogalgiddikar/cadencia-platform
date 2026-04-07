# Cadencia — Frontend UI Development Guide

> **For**: Frontend Engineer  
> **Backend**: FastAPI (**46 API endpoints** — 39 core + 7 wallet integration)  
> **Base URL**: `http://localhost:8000` (dev) / `https://api.cadencia.in` (prod)  
> **Auth**: JWT RS256 — Bearer token in `Authorization` header  
> **Wallet**: Pera Wallet via `@txnlab/use-wallet` + `@perawallet/connect`  
> **Response envelope**: `{ "status": "success", "data": {...} }`

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Authentication Flow](#2-authentication-flow)
3. [Page Map (11 Pages)](#3-page-map-11-pages)
4. [Page 1: Login & Registration](#page-1-login--registration)
5. [Page 2: Dashboard (Home)](#page-2-dashboard-home)
6. [Page 3: Enterprise Profile & Settings](#page-3-enterprise-profile--settings)
6b. [Page 3b: Wallet Management (Pera Wallet)](#page-3b-wallet-management-pera-wallet)
7. [Page 4: Marketplace — RFQ Management](#page-4-marketplace--rfq-management)
8. [Page 5: Marketplace — Seller Capability Profile](#page-5-marketplace--seller-capability-profile)
9. [Page 6: Negotiation Sessions](#page-6-negotiation-sessions)
10. [Page 7: Negotiation Live Room (SSE)](#page-7-negotiation-live-room-sse)
11. [Page 8: Escrow & Settlements](#page-8-escrow--settlements)
12. [Page 9: Compliance & Audit](#page-9-compliance--audit)
13. [Page 10: Admin Panel](#page-10-admin-panel)
14. [API Endpoint Master Reference](#api-endpoint-master-reference)
15. [Shared Components](#shared-components)
16. [State Management & Auth](#state-management--auth)
17. [Design System Guidance](#design-system-guidance)

---

## 1. Architecture Overview

```
+----------------------------------------------------------------------+
|                     CADENCIA FRONTEND (Next.js)                       |
+----------+---------+----------+----------+---------+---------+-------+
| Login/   |Dashboard|Marketplace|Negotiation| Wallet | Escrow |Compli-|
| Register | (Home)  |(RFQ+Match)|(Sessions) | (Pera) |(Settle)|ance   |
+----------+---------+----------+----------+---------+---------+-------+
|                Auth Context (JWT + Refresh)                           |
|                Wallet Context (Pera Wallet SDK)                       |
+----------------------------------------------------------------------+
|                    API Client (axios/fetch)                           |
|              Base URL: /v1/*    Auth: Bearer {token}                 |
+----------------------------------------------------------------------+
            |                    |                    |
    +-------v-------+  +--------v---------+  +------v--------+
    |  Identity API  |  |  Marketplace API  |  | Negotiation   |
    | 8 + 4 wallet   |  |   6 endpoints     |  | 6 endpoints   |
    | = 12 endpoints |  +------------------+  +---------------+
    +----------------+          |                    |
            |           +-------v---------+
    +-------v-------+   |   Compliance    |
    |  Settlement   |   |   8 endpoints   |
    | 7 + 2 wallet  |   +-----------------+
    | = 9 endpoints |
    +---------------+
```

**Total: 11 pages using 41 API endpoints** (+ 1 health + 4 framework = 46)

---

## 2. Authentication Flow

### Token Lifecycle

```
1. User registers/logs in → receives access_token (15 min) + refresh_token (httpOnly cookie, 30 days)
2. All subsequent API calls: Authorization: Bearer {access_token}
3. When access_token expires → POST /v1/auth/refresh → new access_token
4. Store access_token in memory (NOT localStorage) for XSS protection
5. refresh_token is sent automatically as httpOnly cookie
```

### API Client Setup (axios example)

```javascript
const api = axios.create({
  baseURL: 'http://localhost:8000',
  withCredentials: true,  // Send cookies for refresh token
});

// Auto-refresh on 401
api.interceptors.response.use(
  res => res,
  async err => {
    if (err.response?.status === 401 && !err.config._retry) {
      err.config._retry = true;
      const { data } = await api.post('/v1/auth/refresh');
      setAccessToken(data.data.access_token);
      err.config.headers.Authorization = `Bearer ${data.data.access_token}`;
      return api(err.config);
    }
    return Promise.reject(err);
  }
);
```

---

## 3. Page Map (11 Pages)

| # | Page | Route | Endpoints Used | Auth Required |
|---|------|-------|----------------|---------------|
| 1 | Login & Registration | `/login`, `/register` | 3 | ❌ |
| 2 | Dashboard (Home) | `/dashboard` | 5 | ✅ |
| 3 | Enterprise Profile & Settings | `/settings` | 5 | ✅ (ADMIN) |
| 3b | **Wallet Management (Pera Wallet)** | `/settings/wallet` | **4** | ✅ (ADMIN) |
| 4 | Marketplace — RFQ Management | `/marketplace` | 4 | ✅ |
| 5 | Seller Capability Profile | `/marketplace/profile` | 2 | ✅ (Seller) |
| 6 | Negotiation Sessions | `/negotiations` | 3 | ✅ |
| 7 | Negotiation Live Room | `/negotiations/:id` | 4 | ✅ |
| 8 | Escrow & Settlements | `/escrow` | **9** | ✅ |
| 9 | Compliance & Audit | `/compliance` | 8 | ✅ |
| 10 | Admin Panel | `/admin` | 4 | ✅ (ADMIN) |

---

## Page 1: Login & Registration

**Routes**: `/login`, `/register`  
**Auth**: Not required (public pages)

### Endpoints Used

| # | Method | Endpoint | Purpose | When Called |
|---|--------|----------|---------|-------------|
| 1 | `POST` | `/v1/auth/register` | Create enterprise + admin user | "Register" form submit |
| 2 | `POST` | `/v1/auth/login` | Authenticate and get JWT | "Login" form submit |
| 3 | `POST` | `/v1/auth/refresh` | Silent token refresh on page load | Auto on app mount |

### UI Components

#### Login Form
```
┌─────────────────────────────────────┐
│         🏢 Cadencia                  │
│    AI-Powered B2B Trade Platform     │
│                                      │
│  ┌─────────────────────────────┐    │
│  │ 📧 Email                    │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ 🔒 Password                 │    │
│  └─────────────────────────────┘    │
│                                      │
│  [ 🔑 Sign In ]                     │
│                                      │
│  Don't have an account? Register →   │
└─────────────────────────────────────┘
```

#### Registration Form (multi-step)
```
Step 1: Enterprise Info
  - Legal Name (text)
  - PAN (text, 10 chars, e.g. ABCDE1234F)
  - GSTIN (text, 15 chars)
  - Trade Role (dropdown: BUYER / SELLER / BOTH)
  - Industry Vertical (text)
  - Geography (text)
  - Commodities (multi-select tags)
  - Min Order Value (number, INR)
  - Max Order Value (number, INR)

Step 2: Admin User
  - Full Name (text)
  - Email (email)
  - Password (password, min 8 chars)
  - Confirm Password

Step 3: Review & Submit
```

### Request/Response

```javascript
// POST /v1/auth/register
const payload = {
  enterprise: {
    legal_name: "Tata Steel Ltd",
    pan: "ABCDE1234F",
    gstin: "27ABCDE1234F1ZP",
    trade_role: "BUYER",
    commodities: ["HR Coil", "Cold Rolled"],
    min_order_value: 100000,
    max_order_value: 50000000,
    industry_vertical: "Steel Manufacturing",
    geography: "Maharashtra"
  },
  user: {
    email: "admin@tatasteel.com",
    password: "SecurePass123!",
    full_name: "Ratan Tata",
    role: "ADMIN"
  }
};

// Response: { status: "success", data: { access_token: "eyJ...", token_type: "bearer" } }
// refresh_token is set as httpOnly cookie automatically

// POST /v1/auth/login
const loginPayload = {
  email: "admin@tatasteel.com",
  password: "SecurePass123!"
};
// Same response format
```

---

## Page 2: Dashboard (Home)

**Route**: `/dashboard`  
**Auth**: Required

### Endpoints Used

| # | Method | Endpoint | Purpose | When Called |
|---|--------|----------|---------|-------------|
| 1 | `GET` | `/health` | System status indicator | Page load |
| 2 | `GET` | `/v1/enterprises/{id}` | Enterprise profile summary | Page load |
| 3 | `GET` | `/v1/marketplace/rfq/{rfq_id}` | Recent RFQ status (loop) | Page load |
| 4 | `GET` | `/v1/sessions/{session_id}` | Active session count | Page load |
| 5 | `GET` | `/v1/escrow/{session_id}` | Pending escrows | Page load |

### UI Layout

```
┌────────────────────────────────────────────────────────────┐
│  🏢 Tata Steel Ltd          [🔔] [👤 Admin ▾]              │
├──────────┬─────────────────────────────────────────────────┤
│          │                                                  │
│ 📊 Dash  │  Welcome back, Ratan!                           │
│ 🛒 Market│                                                  │
│ 🤝 Nego  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────┐│
│ 💰 Escrow│  │ Active   │ │ Pending │ │ Agreed  │ │ Total ││
│ 📋 Audit │  │ RFQs     │ │ Escrows │ │Sessions │ │ Trades││
│ ⚙️ Admin │  │   12     │ │    3    │ │    7    │ │  45   ││
│          │  └─────────┘ └─────────┘ └─────────┘ └───────┘│
│          │                                                  │
│          │  Recent Activity                                 │
│          │  ───────────────────────────────────────          │
│          │  📦 RFQ #A1B2 - "500MT HR Coil" → MATCHED       │
│          │  🤝 Session #C3D4 - Round 5, awaiting seller     │
│          │  💰 Escrow #E5F6 - ₹2.5Cr FUNDED                │
│          │  ✅ Trade #G7H8 - Completed, FEMA filed          │
│          │                                                  │
│          │  System Health: 🟢 All services operational      │
└──────────┴─────────────────────────────────────────────────┘
```

### Implementation Notes
- Fetch enterprise profile on mount → display in sidebar
- Poll `/health` every 30s → show system status badge
- For "Recent Activity" — fetch last 5 RFQs and sessions, show status timeline

---

## Page 3: Enterprise Profile & Settings

**Route**: `/settings`  
**Auth**: Required (ADMIN role for KYC + agent config)

### Endpoints Used

| # | Method | Endpoint | Purpose | When Called |
|---|--------|----------|---------|-------------|
| 1 | `GET` | `/v1/enterprises/{enterprise_id}` | Load profile (incl. wallet status) | Page load |
| 2 | `PATCH` | `/v1/enterprises/{enterprise_id}/kyc` | Submit KYC docs | Form submit |
| 3 | `PUT` | `/v1/enterprises/{enterprise_id}/agent-config` | Update AI agent behavior | Form submit |
| 4 | `POST` | `/v1/auth/api-keys` | Create M2M API key | Button click |
| 5 | `DELETE` | `/v1/auth/api-keys/{key_id}` | Revoke API key | Button click |

### UI Sections

```
+-- Enterprise Profile ------------------------------------------+
|                                                                 |
|  Legal Name: Tata Steel Ltd                                     |
|  PAN: ABCDE1234F          GSTIN: 27ABCDE1234F1ZP               |
|  Trade Role: BUYER         KYC Status: PENDING                  |
|  Wallet: ALGO...X7Q2 (linked)   Balance: 45.2 ALGO             |
|            [Manage Wallet ->]                                   |
|                                                                 |
|  --- KYC Submission (ADMIN only) -----------------------        |
|  Upload Documents: [Browse...] [ Submit KYC ]                   |
|                                                                 |
|  --- AI Agent Configuration -------------------------           |
|  Negotiation Style:  [ Aggressive v ]                           |
|  Max Rounds:         [ 20 ]                                     |
|  Auto-escalate:      [x] Escalate to human after 15 rounds     |
|  Min Acceptable:     [ Rs _______ ]                             |
|  [ Save Agent Config ]                                          |
|                                                                 |
|  --- API Keys (M2M Authentication) ------------------           |
|  Label: [___________] [ Create Key ]                            |
|                                                                 |
|  | Label        | Key ID         | Created    | Actions  |      |
|  |--------------|----------------|------------|----------|      |
|  | ERP System   | abc-123...     | 2024-01-15 | [Revoke] |      |
|  | Mobile App   | def-456...     | 2024-02-20 | [Revoke] |      |
+-----------------------------------------------------------------+
```

### Key UX Notes
- When API key is created, show the raw key ONCE in a modal with copy button: "This key will never be shown again"
- KYC status badge: NOT_SUBMITTED (red) -> PENDING (amber) -> ACTIVE (green) -> REJECTED (gray)
- **Wallet status** is shown as a summary card linking to **Page 3b** (Wallet Management)
- Enterprise response includes `algorand_wallet` field — if non-null, show truncated address

---

## Page 3b: Wallet Management (Pera Wallet)

**Route**: `/settings/wallet`  
**Auth**: Required (ADMIN role)  
**SDK**: `@txnlab/use-wallet` + `@perawallet/connect`

### Endpoints Used

| # | Method | Endpoint | Purpose | When Called |
|---|--------|----------|---------|-------------|
| 1 | `GET` | `/v1/enterprises/{id}/wallet/challenge` | Generate wallet verification challenge | "Link Wallet" button |
| 2 | `POST` | `/v1/enterprises/{id}/wallet/link` | Submit signed challenge + link wallet | After Pera Wallet signing |
| 3 | `DELETE` | `/v1/enterprises/{id}/wallet` | Unlink wallet from enterprise | "Unlink" button |
| 4 | `GET` | `/v1/enterprises/{id}/wallet/balance` | Query on-chain ALGO balance | Auto on page load (if linked) |

### Security Flow

```
  Frontend (Browser)              Backend               Pera Wallet (Mobile)
  ==================              =======               ====================
       |                              |                          |
  1. Click "Link Wallet"              |                          |
       |--- GET /wallet/challenge --->|                          |
       |<-- { challenge_id,           |                          |
       |      nonce,                  |                          |
       |      message_to_sign,        |                          |
       |      expires_at } -----------|                          |
       |                              |                          |
  2. Sign message via SDK             |                          |
       |------ signBytes(message) ---------------------->        |
       |<----- signature (Ed25519) <--------------------|        |
       |                              |                          |
  3. Submit proof                     |                          |
       |--- POST /wallet/link ------->|                          |
       |    { algorand_address,       |                          |
       |      signature,              |  verify_bytes()          |
       |      challenge_id }          |  delete nonce            |
       |<-- { enterprise with         |  link wallet             |
       |      algorand_wallet } ------|                          |
       |                              |                          |
  4. Query balance                    |                          |
       |--- GET /wallet/balance ----->|                          |
       |<-- { algo_balance_algo,      |  algod.account_info()   |
       |      available_balance,      |                          |
       |      opted_in_apps } --------|                          |
```

> **SECURITY**: The backend NEVER handles or stores user private keys. All signing happens in
> the Pera Wallet mobile app. The backend only verifies signatures using `algosdk.encoding.verify_bytes()`.

### UI Layout

```
+-- Wallet Management (Pera Wallet) -----------------------------+
|                                                                  |
|  --- Wallet Status ----------------------------------------      |
|  +----------------------------------------------------------+   |
|  |                                                          |   |
|  |  [Pera Wallet Icon]                                      |   |
|  |                                                          |   |
|  |  Status: LINKED (green)                                  |   |
|  |  Address: ALGO7X...Q2YK (truncated, click to copy full)  |   |
|  |  Linked: 2024-03-15 14:32 UTC                            |   |
|  |                                                          |   |
|  |  [ Unlink Wallet ]                                       |   |
|  +----------------------------------------------------------+   |
|                                                                  |
|  --- On-Chain Balance --------------------------------           |
|  +----------------------------------------------------------+   |
|  |  Total Balance:      45.230000 ALGO                      |   |
|  |  Min Balance:         0.100000 ALGO                      |   |
|  |  Available:          45.130000 ALGO                      |   |
|  |  Balance (microALGO): 45,230,000                         |   |
|  |                                                          |   |
|  |  Opted-In Applications:                                  |   |
|  |  | App ID    | Name              |                        |   |
|  |  |-----------|-------------------|                        |   |
|  |  | 12345678  | CadenciaEscrow    |                        |   |
|  |  | 98765432  | CadenciaEscrow #2 |                        |   |
|  +----------------------------------------------------------+   |
|                                                                  |
|  [Refresh Balance]                          Last: 2 min ago     |
+-----------------------------------------------------------------+

--- OR (if no wallet linked) ---

+-- Wallet Management (Pera Wallet) -----------------------------+
|                                                                  |
|  +----------------------------------------------------------+   |
|  |                                                          |   |
|  |  [Pera Wallet Icon]                                      |   |
|  |                                                          |   |
|  |  No wallet linked to this enterprise.                    |   |
|  |                                                          |   |
|  |  Link your Algorand wallet to:                           |   |
|  |    * Fund escrow contracts directly from the platform    |   |
|  |    * View on-chain balances                              |   |
|  |    * Track opted-in smart contracts                      |   |
|  |                                                          |   |
|  |  Requirements:                                           |   |
|  |    * Pera Wallet app installed on your mobile device     |   |
|  |    * Algorand account with sufficient ALGO balance       |   |
|  |                                                          |   |
|  |  [ Connect Pera Wallet ]                                 |   |
|  +----------------------------------------------------------+   |
+-----------------------------------------------------------------+
```

### Link Flow (Step-by-Step UX)

```
Step 1: User clicks "Connect Pera Wallet"
  -> Pera Wallet SDK opens QR code / deep link to mobile app
  -> User approves connection in mobile app
  -> SDK returns algorand_address

Step 2: Frontend calls GET /wallet/challenge
  -> Backend returns { challenge_id, nonce, message_to_sign, expires_at }
  -> Show: "Please sign this verification message in Pera Wallet"

Step 3: Frontend calls peraWallet.signBytes(message_to_sign)
  -> Pera Wallet displays message to user
  -> User approves signing on mobile device
  -> SDK returns base64-encoded Ed25519 signature

Step 4: Frontend calls POST /wallet/link
  -> Sends { algorand_address, signature, challenge_id }
  -> Backend verifies signature + links wallet
  -> Success: show wallet balance card
  -> Failure: show error (expired challenge or invalid signature)

Step 5: Frontend calls GET /wallet/balance
  -> Displays ALGO balance, min balance, available balance, opted-in apps
```

### Request/Response Examples

```javascript
// GET /v1/enterprises/{id}/wallet/challenge
// Response:
{
  "status": "success",
  "data": {
    "challenge_id": "wc-a1b2c3d4e5f67890",
    "nonce": "f4a8c9d2e1b0...64-char-hex",
    "message_to_sign": "Cadencia wallet verification: f4a8c9d2e1b0...",
    "expires_at": "2024-03-15T14:37:00Z"  // 5-minute TTL
  }
}

// POST /v1/enterprises/{id}/wallet/link
const linkPayload = {
  algorand_address: "ALGO7XJ3K...58-chars",  // 58-char Algorand address
  signature: "base64-encoded-ed25519-signature",
  challenge_id: "wc-a1b2c3d4e5f67890"
};
// Response: { status: "success", data: { enterprise_id, algorand_wallet, ... } }

// DELETE /v1/enterprises/{id}/wallet
// Response: { status: "success", data: { enterprise_id, message: "Wallet unlinked" } }

// GET /v1/enterprises/{id}/wallet/balance
// Response:
{
  "status": "success",
  "data": {
    "algorand_address": "ALGO7XJ3K...",
    "algo_balance_microalgo": 45230000,
    "algo_balance_algo": "45.230000",
    "min_balance": 100000,
    "available_balance": 45130000,
    "opted_in_apps": [
      { "app_id": 12345678, "app_name": null }
    ]
  }
}
```

### TypeScript Types

```typescript
interface WalletChallenge {
  challenge_id: string;
  nonce: string;
  message_to_sign: string;
  expires_at: string; // ISO 8601
}

interface WalletLinkRequest {
  algorand_address: string; // 58 chars
  signature: string;        // base64 Ed25519
  challenge_id: string;
}

interface WalletBalance {
  algorand_address: string;
  algo_balance_microalgo: number;
  algo_balance_algo: string;
  min_balance: number;
  available_balance: number;
  opted_in_apps: OptedInApp[];
}

interface OptedInApp {
  app_id: number;
  app_name: string | null;
}
```

### Frontend SDK Setup

```typescript
// lib/pera.ts
import { PeraWalletConnect } from '@perawallet/connect';

export const peraWallet = new PeraWalletConnect({
  shouldShowSignTxnToast: true,
});

// hooks/useWallet.ts
import { useState, useCallback } from 'react';
import { peraWallet } from '@/lib/pera';
import { api } from '@/lib/api';

export function useWallet(enterpriseId: string) {
  const [status, setStatus] = useState<'idle' | 'connecting' | 'signing' | 'linked' | 'error'>('idle');
  const [balance, setBalance] = useState<WalletBalance | null>(null);
  const [error, setError] = useState<string | null>(null);

  const connectAndLink = useCallback(async () => {
    try {
      setStatus('connecting');
      // 1. Connect Pera Wallet
      const accounts = await peraWallet.connect();
      const address = accounts[0];

      // 2. Get challenge from backend
      const { data: challenge } = await api.get(
        `/v1/enterprises/${enterpriseId}/wallet/challenge`
      );

      setStatus('signing');
      // 3. Sign challenge message
      const msgBytes = new TextEncoder().encode(challenge.data.message_to_sign);
      const signedBytes = await peraWallet.signData(
        [{ data: msgBytes, message: 'Verify wallet ownership' }],
        address
      );
      const signature = btoa(String.fromCharCode(...signedBytes[0]));

      // 4. Link wallet
      await api.post(`/v1/enterprises/${enterpriseId}/wallet/link`, {
        algorand_address: address,
        signature,
        challenge_id: challenge.data.challenge_id,
      });

      setStatus('linked');
      await fetchBalance();
    } catch (err: any) {
      setStatus('error');
      setError(err.response?.data?.detail || err.message);
    }
  }, [enterpriseId]);

  const fetchBalance = useCallback(async () => {
    const { data } = await api.get(
      `/v1/enterprises/${enterpriseId}/wallet/balance`
    );
    setBalance(data.data);
  }, [enterpriseId]);

  const unlinkWallet = useCallback(async () => {
    await api.delete(`/v1/enterprises/${enterpriseId}/wallet`);
    setStatus('idle');
    setBalance(null);
  }, [enterpriseId]);

  return { status, balance, error, connectAndLink, fetchBalance, unlinkWallet };
}
```

### Key UX Notes
- **Challenge expiry**: nonces expire in 5 minutes — show a countdown timer
- **Error handling**: if signature verification fails (403), show "Invalid signature or expired challenge. Please try again."
- **Balance refresh**: auto-refresh every 60 seconds when wallet is linked; show last-refreshed timestamp
- **Unlink confirmation**: show a confirmation dialog before unlinking
- **Mobile deep link**: Pera Wallet SDK handles QR code (desktop) or deep link (mobile) automatically

---

## Page 4: Marketplace — RFQ Management

**Route**: `/marketplace`  
**Auth**: Required

### Endpoints Used

| # | Method | Endpoint | Purpose | When Called |
|---|--------|----------|---------|-------------|
| 1 | `POST` | `/v1/marketplace/rfq` | Upload new RFQ | Form submit |
| 2 | `GET` | `/v1/marketplace/rfq/{rfq_id}` | View RFQ details + parsed fields | Row click |
| 3 | `GET` | `/v1/marketplace/rfq/{rfq_id}/matches` | View ranked seller matches | When RFQ status = MATCHED |
| 4 | `POST` | `/v1/marketplace/rfq/{rfq_id}/confirm` | Confirm match → start negotiation | "Confirm" button |

### UI Layout

```
┌─ Marketplace — Request for Quotations ────────────────────┐
│                                                            │
│  [ + New RFQ ]                            🔍 Filter: [All]│
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ RFQ Upload Form (expandable)                         │  │
│  │                                                      │  │
│  │ Describe your requirement in natural language:       │  │
│  │ ┌──────────────────────────────────────────────────┐ │  │
│  │ │ "Need 500 metric tons of HR Coil, IS 2062 grade, │ │  │
│  │ │  delivery to Mumbai port within 45 days.          │ │  │
│  │ │  Budget: ₹38,000-42,000 per MT."                  │ │  │
│  │ └──────────────────────────────────────────────────┘ │  │
│  │ [ 🚀 Submit RFQ ]                                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ─── Your RFQs ─────────────────────────────────────       │
│  | RFQ ID    | Product       | Status   | Matches | Actions│
│  |───────────|───────────────|──────────|─────────|────────│
│  | #A1B2     | HR Coil 500MT | 🟢MATCHED|    5    | [View] │
│  | #C3D4     | Cold Rolled   | 🟡PARSED |    -    | [View] │
│  | #E5F6     | Wire Rod      | ⚪DRAFT  |    -    | [View] │
│  | #G7H8     | HR Coil 200MT | ✅CONFIRMED|  1    | [View] │
│                                                            │
│  ─── RFQ Detail Panel (when row selected) ───────────      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ RFQ #A1B2 — HR Coil                                  │  │
│  │ Status: MATCHED                                       │  │
│  │                                                       │  │
│  │ Parsed Fields (AI-extracted):                         │  │
│  │   Product: HR Coil     HSN: 72083990                  │  │
│  │   Quantity: 500 MT     Budget: ₹38K-42K/MT            │  │
│  │   Delivery: 45 days    Geography: Mumbai              │  │
│  │                                                       │  │
│  │ Matched Sellers (ranked by AI similarity):            │  │
│  │ | Rank | Seller           | Score  | Action          |│  │
│  │ |──────|──────────────────|────────|─────────────────|│  │
│  │ | 1    | JSW Steel Ltd    | 94.2%  | [✅ Confirm]    |│  │
│  │ | 2    | SAIL Corp        | 87.5%  | [✅ Confirm]    |│  │
│  │ | 3    | Arcelor Mittal   | 81.3%  | [✅ Confirm]    |│  │
│  │                                                       │  │
│  │ ⚡ Confirming starts AI-powered negotiation           │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### Key UX Notes
- RFQ submission returns **202 Accepted** (async) — show spinner, poll `GET /rfq/{id}` until status changes from `DRAFT` → `PARSED` → `MATCHED`
- Polling interval: every 3 seconds while status is `DRAFT` or `PARSED`
- When confirming a match, show confirmation dialog: "This will start an AI negotiation session with {seller_name}. Proceed?"

---

## Page 5: Marketplace — Seller Capability Profile

**Route**: `/marketplace/profile`  
**Auth**: Required (Seller role)

### Endpoints Used

| # | Method | Endpoint | Purpose | When Called |
|---|--------|----------|---------|-------------|
| 1 | `PUT` | `/v1/marketplace/capability-profile` | Update seller profile | Form submit |
| 2 | `POST` | `/v1/marketplace/capability-profile/embeddings` | Trigger embedding recompute | After profile update |

### UI Layout

```
┌─ Seller Capability Profile ───────────────────────────────┐
│                                                            │
│  Tell AI about your capabilities so buyers can find you:   │
│                                                            │
│  Industry:   [ Steel Manufacturing ▾ ]                     │
│  Products:   [ HR Coil ] [ Cold Rolled ] [ Wire Rod ] [+]  │
│  Geography:  [ Maharashtra ] [ Gujarat ] [ Karnataka ] [+] │
│  Min Order:  [ ₹ 1,00,000 ]                               │
│  Max Order:  [ ₹ 50,00,00,000 ]                           │
│                                                            │
│  Free-text description (used for AI matching):             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ "We are a leading HR Coil manufacturer with 2MT/day  │  │
│  │  capacity. ISO 9001 certified. Deliver pan-India     │  │
│  │  within 30 days. Competitive pricing for bulk."      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  [ 💾 Save Profile ]   Embedding: 🟢 Active (last: 2h ago)│
└────────────────────────────────────────────────────────────┘
```

---

## Page 6: Negotiation Sessions

**Route**: `/negotiations`  
**Auth**: Required

### Endpoints Used

| # | Method | Endpoint | Purpose | When Called |
|---|--------|----------|---------|-------------|
| 1 | `POST` | `/v1/sessions` | Create session (auto via RFQ confirm) | Rarely manual |
| 2 | `GET` | `/v1/sessions/{session_id}` | List/view sessions | Page load (loop over IDs) |
| 3 | `POST` | `/v1/sessions/{session_id}/terminate` | Admin terminate | Button click (ADMIN) |

### UI Layout

```
┌─ Negotiation Sessions ────────────────────────────────────┐
│                                                            │
│  Filter: [All ▾]  [Active ▾]  [This Week ▾]              │
│                                                            │
│  | Session  | Buyer ↔ Seller     | Status  | Rounds | Btn │
│  |──────────|────────────────────|─────────|────────|─────│
│  | #S001    | You ↔ JSW Steel    | 🟢ACTIVE|  5/20  |[▶️] │
│  | #S002    | You ↔ SAIL Corp    | ✅AGREED|  12/20 |[📋] │
│  | #S003    | Hindalco ↔ You     | ⏳STALLED|  8/20  |[⚠️] │
│  | #S004    | You ↔ Arcelor      | ❌FAILED|  20/20 |[📋] │
│                                                            │
│  Click ▶️ to enter live negotiation room                   │
│  Click 📋 to view completed session details                │
└────────────────────────────────────────────────────────────┘
```

### Key UX Notes
- Active sessions show a pulsing green indicator
- STALLED sessions show ⚠️ with "Needs human review" label
- Clicking a row navigates to the Live Room (Page 7)

---

## Page 7: Negotiation Live Room (SSE)

**Route**: `/negotiations/:session_id`  
**Auth**: Required  
**⚡ This is the most complex page — uses Server-Sent Events (SSE)**

### Endpoints Used

| # | Method | Endpoint | Purpose | When Called |
|---|--------|----------|---------|-------------|
| 1 | `GET` | `/v1/sessions/{session_id}` | Load session state | Page load |
| 2 | `GET` | `/v1/sessions/{session_id}/stream` | SSE live event stream | On mount (EventSource) |
| 3 | `POST` | `/v1/sessions/{session_id}/turn` | Trigger next agent turn | "Next Turn" button |
| 4 | `POST` | `/v1/sessions/{session_id}/override` | Human injects offer | "Override" form submit |

### UI Layout

```
┌─ Negotiation #S001 — You (Buyer) ↔ JSW Steel (Seller) ───┐
│                                                            │
│  Status: 🟢 ACTIVE    Round: 5 / 20    ⏱️ Expires: 23h    │
│                                                            │
│  ┌──── Negotiation Timeline ────────────────────────────┐  │
│  │                                                      │  │
│  │  🤖 Buyer Agent (Round 1)              ₹38,000/MT   │  │
│  │  ├─ Initial offer based on budget range              │  │
│  │  │  Terms: FOB Mumbai, 45 days delivery              │  │
│  │  │  Confidence: 72%                                  │  │
│  │  │                                                   │  │
│  │  🤖 Seller Agent (Round 2)              ₹44,500/MT   │  │
│  │  ├─ Counter at list price                            │  │
│  │  │  Terms: Ex-works, 60 days delivery                │  │
│  │  │  Confidence: 85%                                  │  │
│  │  │                                                   │  │
│  │  🤖 Buyer Agent (Round 3)              ₹39,500/MT   │  │
│  │  ├─ Increased by 3.9%                               │  │
│  │  │                                                   │  │
│  │  🤖 Seller Agent (Round 4)              ₹42,000/MT   │  │
│  │  ├─ Reduced by 5.6%                                 │  │
│  │  │                                                   │  │
│  │  🤖 Buyer Agent (Round 5)              ₹40,200/MT   │  │
│  │  ├─ ⏳ Waiting for seller response...                │  │
│  │  │     ● ● ●  (animated dots)                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──── Price Convergence Chart ─────────────────────────┐  │
│  │  ₹45K ─ · · · · · ·                                 │  │
│  │  ₹43K ─     ╲                                        │  │
│  │  ₹41K ─       ╲  ╱ ← converging                     │  │
│  │  ₹39K ─  ╱  ╱                                        │  │
│  │  ₹37K ─ · · · · · ·                                 │  │
│  │         R1  R2  R3  R4  R5                            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──── Actions ─────────────────────────────────────────┐  │
│  │  [ ▶️ Next Turn ]    [ 🙋 Human Override ]  [ ⏹️ End ]│  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──── Human Override Panel (expandable) ───────────────┐  │
│  │  Price: ₹ [_________]   Currency: [INR ▾]            │  │
│  │  Terms: {                                            │  │
│  │    "delivery": "FOB Mumbai",                         │  │
│  │    "payment": "LC at sight"                          │  │
│  │  }                                                   │  │
│  │  [ 📤 Submit Override ]                              │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### SSE Implementation

```javascript
// Connect to SSE stream
const eventSource = new EventSource(
  `${BASE_URL}/v1/sessions/${sessionId}/stream`,
  { headers: { Authorization: `Bearer ${token}` } }  // Note: EventSource doesn't support headers natively
);

// Alternative: use fetch API for SSE with auth headers
const response = await fetch(`/v1/sessions/${sessionId}/stream`, {
  headers: { Authorization: `Bearer ${token}` },
});
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const text = decoder.decode(value);
  // Parse SSE format: "id: ...\nevent: ...\ndata: {...}\n\n"
  const events = parseSSE(text);
  events.forEach(event => {
    switch (event.event) {
      case 'new_offer':
        addOfferToTimeline(event.data);
        break;
      case 'session_agreed':
        showAgreementCelebration(event.data);
        break;
      case 'session_failed':
        showFailureNotice(event.data);
        break;
      case 'stall_detected':
        showHumanReviewBanner();
        break;
    }
  });
}
```

### Key UX Notes
- **Price convergence chart**: real-time line chart (buyer line going up, seller line going down — converging)
- **SSE reconnection**: if connection drops, reconnect with `Last-Event-ID` header for replay
- **Celebration**: when session reaches AGREED → confetti animation + show agreed price prominently
- **"Next Turn"**: triggers `POST /v1/sessions/{id}/turn` — shows spinner until SSE event arrives

---

## Page 8: Escrow & Settlements

**Route**: `/escrow`  
**Auth**: Required  
**Wallet**: Pera Wallet SDK for escrow funding (replaces mnemonic input)

### Endpoints Used

| # | Method | Endpoint | Purpose | When Called |
|---|--------|----------|---------|-------------|
| 1 | `GET` | `/v1/escrow/{session_id}` | View escrow state | Page load |
| 2 | `POST` | `/v1/escrow/{session_id}/deploy` | Deploy Algorand contract | "Deploy" button (ADMIN) |
| 3 | `POST` | `/v1/escrow/{escrow_id}/fund` | Fund escrow (legacy/testing) | Admin-only fallback |
| 4 | `POST` | `/v1/escrow/{escrow_id}/release` | Release to seller | "Release" button (ADMIN) |
| 5 | `POST` | `/v1/escrow/{escrow_id}/refund` | Refund buyer | "Refund" button (ADMIN) |
| 6 | `POST` | `/v1/escrow/{escrow_id}/freeze` | Freeze escrow | "Freeze" button |
| 7 | `GET` | `/v1/escrow/{escrow_id}/settlements` | View settlement records | Tab click |
| 8 | `GET` | `/v1/escrow/{escrow_id}/build-fund-txn` | **Build unsigned atomic group for Pera Wallet** | "Fund via Wallet" button |
| 9 | `POST` | `/v1/escrow/{escrow_id}/submit-signed-fund` | **Submit Pera Wallet pre-signed transactions** | After wallet signing |

### UI Layout

```
+-- Escrow & Settlement -----------------------------------------+
|                                                                 |
|  +---- Escrow Pipeline ------------------------------------+    |
|  |                                                         |    |
|  |  DEPLOYED --> FUNDED --> RELEASED    (success path)     |    |
|  |     |           |          |                            |    |
|  |  [Deploy]   [Fund via     [Release]                     |    |
|  |             Pera Wallet]                                |    |
|  |                                                         |    |
|  |  Current: FUNDED (green) (Rs 2,01,00,000)               |    |
|  |  Contract: Algorand App #12345678                       |    |
|  |  Buyer: Tata Steel   Seller: JSW Steel                  |    |
|  +---------------------------------------------------------+    |
|                                                                 |
|  +---- Pera Wallet Funding (NEW) -------------------------+    |
|  |                                                         |    |
|  |  Step 1: [Build Transaction]   Status: READY            |    |
|  |  Step 2: Sign in Pera Wallet   Status: PENDING          |    |
|  |  Step 3: Submit to Algorand    Status: PENDING          |    |
|  |                                                         |    |
|  |  Progress: [=====>                  ] 33%               |    |
|  |                                                         |    |
|  |  Transaction Group:                                     |    |
|  |    [0] PaymentTxn: Buyer -> Escrow App (45.23 ALGO)     |    |
|  |    [1] AppCallTxn: fund() on App #12345678              |    |
|  |  Group ID: base64-encoded-gid                           |    |
|  |                                                         |    |
|  |  [ Fund via Pera Wallet ]                               |    |
|  +---------------------------------------------------------+    |
|                                                                 |
|  +---- Active Escrows ----------------------------------------+  |
|  | Session  | Amount       | Status     | Blockchain   | Fund |  |
|  |----------|--------------|------------|--------------|------|  |
|  | #S001    | Rs 2.01 Cr   | FUNDED     | App #123456  | Done |  |
|  | #S002    | Rs 85.5 L    | RELEASED   | App #789012  | Done |  |
|  | #S003    | Rs 45.2 L    | DEPLOYED   | App #345678  | [->] |  |
|  +-------------------------------------------------------------+  |
|                                                                 |
|  +---- Settlement Records (for selected escrow) -------------+  |
|  | Type    | Amount     | Tx ID           | Date      |        |
|  |---------|------------|-----------------|-----------|        |
|  | RELEASE | Rs 2.01 Cr | ALGO-TX-abc123  | 2024-03   |        |
|  | MERKLE  | -          | ALGO-TX-def456  | 2024-03   |        |
|  +-------------------------------------------------------------+  |
|                                                                 |
|  Actions: [Fund via Wallet] [Release] [Refund] [Freeze]        |
+-----------------------------------------------------------------+
```

### Pera Wallet Funding Flow

```javascript
// 1. Build unsigned transaction group
const buildResp = await api.get(`/v1/escrow/${escrowId}/build-fund-txn`);
// Response:
// {
//   "unsigned_transactions": ["base64-txn-0", "base64-txn-1"],
//   "group_id": "base64-encoded-group-id",
//   "transaction_count": 2,
//   "description": "Atomic group: [PaymentTxn, AppCallTxn(fund)]"
// }

// 2. Sign with Pera Wallet
import { peraWallet } from '@/lib/pera';
const unsignedTxns = buildResp.data.data.unsigned_transactions;
// Decode base64 -> Uint8Array for Pera SDK
const txnBytes = unsignedTxns.map(b64 => Uint8Array.from(atob(b64), c => c.charCodeAt(0)));
const signedTxns = await peraWallet.signTransaction([txnBytes]);
// signedTxns: Uint8Array[] — signed by user in Pera Wallet app

// 3. Submit signed transactions to backend
const signedB64 = signedTxns.map(s => btoa(String.fromCharCode(...s)));
const submitResp = await api.post(`/v1/escrow/${escrowId}/submit-signed-fund`, {
  signed_transactions: signedB64
});
// Response:
// { "tx_id": "ALGO-TX-abc123", "confirmed_round": 12345678 }
```

### TypeScript Types (Escrow Wallet)

```typescript
interface BuildFundTxnResponse {
  unsigned_transactions: string[];  // base64 encoded
  group_id: string;                 // base64 atomic group ID
  transaction_count: number;
  description: string;
}

interface SubmitSignedFundRequest {
  signed_transactions: string[];    // base64 signed txns from Pera
}

interface SubmitSignedFundResponse {
  tx_id: string;                    // Algorand transaction ID
  confirmed_round: number;          // block number
}
```

### Key UX Notes
- **Primary funding method**: Pera Wallet ("Fund via Pera Wallet" button)
- **Legacy method**: mnemonic input is kept as a fallback for admin/testing (`POST /fund`) — show behind an "Advanced" toggle
- Show escrow state machine as a visual pipeline (horizontal stepper)
- **Pera Wallet funding** is a 3-step wizard with progress indicator:
  1. Build Transaction (automatic, shows group details)
  2. Sign in Pera Wallet (user approves on mobile — show pending spinner)
  3. Submit to Algorand (show confirmation with tx ID and block round)
- Algorand transaction IDs should be clickable links to AlgoExplorer/Pera Explorer
- **Dry-run simulation**: backend automatically runs simulation before broadcasting — if rejected, show error to user
- After successful funding, escrow status transitions `DEPLOYED -> FUNDED` — refresh escrow list

---

## Page 9: Compliance & Audit

**Route**: `/compliance`  
**Auth**: Required

### Endpoints Used

| # | Method | Endpoint | Purpose | When Called |
|---|--------|----------|---------|-------------|
| 1 | `GET` | `/v1/audit/{escrow_id}` | Paginated audit log | Page load |
| 2 | `GET` | `/v1/audit/{escrow_id}/verify` | Verify hash chain integrity | "Verify" button |
| 3 | `GET` | `/v1/compliance/{escrow_id}/fema` | View FEMA record | Tab click |
| 4 | `GET` | `/v1/compliance/{escrow_id}/gst` | View GST record | Tab click |
| 5 | `GET` | `/v1/compliance/{escrow_id}/fema/pdf` | Download FEMA PDF | "Download" button |
| 6 | `GET` | `/v1/compliance/{escrow_id}/gst/csv` | Download GST CSV | "Download" button |
| 7 | `POST` | `/v1/compliance/export/zip` | Bulk export (ADMIN) | "Export All" button |

### UI Layout

```
┌─ Compliance & Audit Trail ────────────────────────────────┐
│                                                            │
│  Select Escrow: [ #S001 — Tata ↔ JSW ▾ ]                 │
│                                                            │
│  ┌──── Tabs ────────────────────────────────────────────┐  │
│  │ [📋 Audit Log] [🏛️ FEMA] [📊 GST] [📦 Bulk Export]  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ── Audit Log Tab ──────────────────────────────────────   │
│  Chain Integrity: 🟢 VALID (47 entries verified)          │
│  [ 🔍 Verify Chain ]                                      │
│                                                            │
│  | # | Event Type      | Actor       | Timestamp         |│
│  |───|─────────────────|─────────────|───────────────────|│
│  | 47| ESCROW_RELEASED | system      | 2024-03-15 14:32  |│
│  | 46| MERKLE_ANCHORED | system      | 2024-03-15 14:32  |│
│  | 45| ESCROW_FUNDED   | buyer_admin | 2024-03-14 09:15  |│
│  | 44| SESSION_AGREED  | ai_agent    | 2024-03-13 16:45  |│
│  | ...                                                    |│
│  [ Load More... ] (cursor-based pagination)               │
│                                                            │
│  ── FEMA Tab ───────────────────────────────────────────   │
│  FEMA Record: ✅ Filed                                     │
│  Transaction Type: GOODS_IMPORT                            │
│  Purpose Code: P0103                                       │
│  Amount: ₹2,01,00,000    Currency: INR                     │
│  [ 📥 Download FEMA PDF ]                                  │
│                                                            │
│  ── GST Tab ────────────────────────────────────────────   │
│  GST Record: ✅ Filed (Interstate)                         │
│  Place of Supply: Maharashtra                              │
│  IGST: ₹36,18,000 (18%)                                   │
│  [ 📥 Download GST CSV ]                                   │
│                                                            │
│  ── Bulk Export Tab (ADMIN only) ───────────────────────   │
│  Select escrows for bulk export:                           │
│  [✓] #S001   [✓] #S002   [ ] #S003   [ ] #S004           │
│  [ 📦 Export ZIP ]   Status: ✅ Ready (download link)      │
└────────────────────────────────────────────────────────────┘
```

### Key UX Notes
- Audit log uses **cursor-based pagination** — pass `cursor` param for "Load More"
- Chain verification: show animated spinner during verification, then 🟢/🔴 result
- PDF/CSV downloads trigger browser download (streaming response)
- Bulk ZIP: returns 202 → poll or wait, then download from Redis URL

---

## Page 10: Admin Panel

**Route**: `/admin`  
**Auth**: Required (ADMIN role only)

### Endpoints Used

| # | Method | Endpoint | Purpose | When Called |
|---|--------|----------|---------|-------------|
| 1 | `GET` | `/health` | System health dashboard | Auto-refresh |
| 2 | `POST` | `/v1/auth/api-keys` | Manage API keys | Settings tab |
| 3 | `DELETE` | `/v1/auth/api-keys/{key_id}` | Revoke keys | Settings tab |
| 4 | `POST` | `/v1/compliance/export/zip` | Bulk compliance export | Compliance tab |

### UI Layout
- **System Health**: real-time dashboard showing DB, Redis, Algorand, LLM, circuits status
- **API Keys**: CRUD management
- **Compliance Export**: bulk operations
- Only accessible if `user.role === 'ADMIN'`

---

## API Endpoint Master Reference

### Identity (8 core + 4 wallet = 12 endpoints)

| # | Method | Path | Page(s) | Auth |
|---|--------|------|---------|------|
| 1 | `POST` | `/v1/auth/register` | Login/Register | No |
| 2 | `POST` | `/v1/auth/login` | Login/Register | No |
| 3 | `POST` | `/v1/auth/refresh` | All (auto-refresh) | Cookie |
| 4 | `POST` | `/v1/auth/api-keys` | Settings, Admin | Yes |
| 5 | `DELETE` | `/v1/auth/api-keys/{key_id}` | Settings, Admin | Yes |
| 6 | `GET` | `/v1/enterprises/{id}` | Dashboard, Settings | Yes |
| 7 | `PATCH` | `/v1/enterprises/{id}/kyc` | Settings | Yes ADMIN |
| 8 | `PUT` | `/v1/enterprises/{id}/agent-config` | Settings | Yes ADMIN |
| **9** | **`GET`** | **`/v1/enterprises/{id}/wallet/challenge`** | **Wallet** | **Yes ADMIN** |
| **10** | **`POST`** | **`/v1/enterprises/{id}/wallet/link`** | **Wallet** | **Yes ADMIN** |
| **11** | **`DELETE`** | **`/v1/enterprises/{id}/wallet`** | **Wallet** | **Yes ADMIN** |
| **12** | **`GET`** | **`/v1/enterprises/{id}/wallet/balance`** | **Wallet, Dashboard** | **Yes** |

### Marketplace (6 endpoints)

| # | Method | Path | Page(s) | Auth |
|---|--------|------|---------|------|
| 13 | `POST` | `/v1/marketplace/rfq` | Marketplace | Yes |
| 14 | `GET` | `/v1/marketplace/rfq/{id}` | Marketplace, Dashboard | Yes |
| 15 | `GET` | `/v1/marketplace/rfq/{id}/matches` | Marketplace | Yes |
| 16 | `POST` | `/v1/marketplace/rfq/{id}/confirm` | Marketplace | Yes |
| 17 | `PUT` | `/v1/marketplace/capability-profile` | Seller Profile | Yes |
| 18 | `POST` | `/v1/marketplace/capability-profile/embeddings` | Seller Profile | Yes |

### Negotiation (6 endpoints)

| # | Method | Path | Page(s) | Auth |
|---|--------|------|---------|------|
| 19 | `POST` | `/v1/sessions` | Negotiation List | Yes |
| 20 | `GET` | `/v1/sessions/{id}` | Negotiation List, Live Room, Dashboard | Yes |
| 21 | `POST` | `/v1/sessions/{id}/turn` | Live Room | Yes |
| 22 | `POST` | `/v1/sessions/{id}/override` | Live Room | Yes |
| 23 | `POST` | `/v1/sessions/{id}/terminate` | Negotiation List | Yes ADMIN |
| 24 | `GET` | `/v1/sessions/{id}/stream` | Live Room (SSE) | Yes |

### Settlement (7 core + 2 wallet = 9 endpoints)

| # | Method | Path | Page(s) | Auth |
|---|--------|------|---------|------|
| 25 | `GET` | `/v1/escrow/{session_id}` | Escrow, Dashboard | Yes |
| 26 | `POST` | `/v1/escrow/{session_id}/deploy` | Escrow | Yes ADMIN |
| 27 | `POST` | `/v1/escrow/{id}/fund` | Escrow (legacy) | Yes ADMIN |
| 28 | `POST` | `/v1/escrow/{id}/release` | Escrow | Yes ADMIN |
| 29 | `POST` | `/v1/escrow/{id}/refund` | Escrow | Yes ADMIN |
| 30 | `POST` | `/v1/escrow/{id}/freeze` | Escrow | Yes |
| 31 | `GET` | `/v1/escrow/{id}/settlements` | Escrow | Yes |
| **32** | **`GET`** | **`/v1/escrow/{id}/build-fund-txn`** | **Escrow (Pera Wallet)** | **Yes** |
| **33** | **`POST`** | **`/v1/escrow/{id}/submit-signed-fund`** | **Escrow (Pera Wallet)** | **Yes** |

### Compliance (8 endpoints)

| # | Method | Path | Page(s) | Auth |
|---|--------|------|---------|------|
| 34 | `GET` | `/v1/audit/{escrow_id}` | Compliance | Yes |
| 35 | `GET` | `/v1/audit/{escrow_id}/verify` | Compliance | Yes |
| 36 | `GET` | `/v1/compliance/{escrow_id}/fema` | Compliance | Yes |
| 37 | `GET` | `/v1/compliance/{escrow_id}/gst` | Compliance | Yes |
| 38 | `GET` | `/v1/compliance/{escrow_id}/fema/pdf` | Compliance | Yes |
| 39 | `GET` | `/v1/compliance/{escrow_id}/gst/csv` | Compliance | Yes |
| 40 | `POST` | `/v1/compliance/export/zip` | Compliance, Admin | Yes ADMIN |

### Infrastructure (1 endpoint)

| # | Method | Path | Page(s) | Auth |
|---|--------|------|---------|------|
| 41 | `GET` | `/health` | Dashboard, Admin | No |

> **Total: 41 direct API endpoints + 5 framework routes = 46 routes**
> **Wallet endpoints: 6 new** (4 identity + 2 settlement) — marked in bold above

---

## Shared Components

Build these reusable components first:

| Component | Used In | Purpose |
|-----------|---------|---------|
| `<Sidebar />` | All pages | Navigation with role-based menu items |
| `<TopBar />` | All pages | User avatar, notifications, enterprise name |
| `<AuthGuard />` | All protected pages | Redirect to `/login` if no token |
| `<AdminGuard />` | Settings, Admin | Check `user.role === 'ADMIN'` |
| `<StatusBadge />` | Marketplace, Negotiation, Escrow | Colored status pill |
| `<DataTable />` | All list views | Sortable, filterable table |
| `<LoadMore />` | Audit log | Cursor-based pagination button |
| `<PriceDisplay />` | Marketplace, Negotiation, Escrow | Formatted currency |
| `<TimelineCard />` | Live Room | Single negotiation round entry |
| `<PriceChart />` | Live Room | Convergence line chart |
| `<FileDownload />` | Compliance | Handle streaming file downloads |
| `<ConfirmDialog />` | Escrow actions, RFQ confirm, Wallet unlink | "Are you sure?" modal |
| `<SecureInput />` | Escrow fund (legacy mnemonic) | Masked input with paste support |
| `<SSEProvider />` | Live Room | EventSource wrapper with reconnect |
| `<EmptyState />` | All lists | "No data yet" illustration |
| `<Toast />` | Global | Success/error notifications |
| **`<WalletCard />`** | **Settings, Dashboard** | **Wallet status summary (linked/unlinked, truncated address)** |
| **`<WalletLinkFlow />`** | **Wallet page** | **3-step wizard: connect -> sign -> link** |
| **`<WalletBalance />`** | **Wallet page, Dashboard** | **ALGO balance, min balance, opted-in apps** |
| **`<PeraFundFlow />`** | **Escrow page** | **3-step Pera Wallet funding: build -> sign -> submit** |
| **`<WalletProvider />`** | **App layout (root)** | **Pera Wallet SDK context wrapper** |

---

## State Management & Auth

### Recommended Stack
- **Framework**: Next.js 14+ (App Router)
- **State**: React Context (auth + wallet) + React Query/TanStack Query (server state)
- **HTTP**: axios with interceptors (auto-refresh, error handling)
- **SSE**: Custom hook `useSSE(sessionId)` wrapping EventSource
- **Wallet**: `@txnlab/use-wallet` + `@perawallet/connect` + `algosdk`
- **Forms**: React Hook Form + Zod validation

### Auth Context Shape
```typescript
interface AuthContext {
  user: { id: string; email: string; role: string; enterprise_id: string } | null;
  accessToken: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterPayload) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
  isBuyer: boolean;
  isSeller: boolean;
}
```

### Wallet Context Shape
```typescript
interface WalletContext {
  // Connection state
  isConnected: boolean;
  connectedAddress: string | null;
  
  // Linking state (enterprise -> wallet)
  isLinked: boolean;              // Enterprise has algorand_wallet set
  linkedAddress: string | null;   // From enterprise profile
  
  // Balance
  balance: WalletBalance | null;
  isLoadingBalance: boolean;
  
  // Actions
  connectAndLink: () => Promise<void>;
  unlinkWallet: () => Promise<void>;
  refreshBalance: () => Promise<void>;
  signAndSubmitFundTxn: (escrowId: string) => Promise<SubmitSignedFundResponse>;
  
  // Status
  status: 'idle' | 'connecting' | 'signing' | 'submitting' | 'linked' | 'error';
  error: string | null;
}
```

---

## Design System Guidance

### Color Palette
```
Primary:    #6366F1 (Indigo-500)   — buttons, links, active states
Secondary:  #0EA5E9 (Sky-500)     — marketplace, info
Success:    #22C55E (Green-500)    — AGREED, RELEASED, VALID, healthy
Warning:    #F59E0B (Amber-500)    — PENDING, STALLED, HALF_OPEN
Danger:     #EF4444 (Red-500)     — FAILED, REJECTED, OPEN, errors
Background: #0F172A (Slate-900)    — dark mode base
Surface:    #1E293B (Slate-800)    — card backgrounds
Text:       #F8FAFC (Slate-50)     — primary text
Muted:      #94A3B8 (Slate-400)    — secondary text
```

### Typography
- Headings: **Inter** (Google Font), semibold
- Body: **Inter**, regular
- Monospace (IDs, hashes): **JetBrains Mono**

### Status Colors (consistent across all pages)
```
DRAFT / NOT_SUBMITTED:  gray circle
PENDING / PARSED:       amber circle
ACTIVE / FUNDED:        green circle
MATCHED / DEPLOYED:     blue circle
AGREED / RELEASED:      green checkmark
FAILED / REJECTED:      red X
FROZEN / STALLED:       orange warning
WALLET_LINKED:          indigo circle (Pera Wallet icon)
WALLET_UNLINKED:        gray dashed circle
SIGNING:                amber pulse animation
```

### NPM Dependencies (Wallet)
```json
{
  "@perawallet/connect": "^1.3.0",
  "@txnlab/use-wallet": "^3.0.0",
  "algosdk": "^2.7.0"
}
```
