// ─── Auth & Users ──────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'ADMIN' | 'USER';
  enterprise_id: string | null;
}

export interface Enterprise {
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

export interface AgentConfig {
  negotiation_style: 'AGGRESSIVE' | 'MODERATE' | 'CONSERVATIVE';
  max_rounds: number;
  auto_escalate: boolean;
  min_acceptable_price: number | null;
}

export interface ApiKey {
  id: string;
  label: string;
  created_at: string;
}

// ─── Wallet ────────────────────────────────────────────────────────────────

export interface WalletChallenge {
  challenge_id: string;
  nonce: string;
  message_to_sign: string;
  expires_at: string;
}

export interface WalletBalance {
  algorand_address: string;
  algo_balance_microalgo: number;
  algo_balance_algo: string;
  min_balance: number;
  available_balance: number;
  opted_in_apps: OptedInApp[];
}

export interface OptedInApp {
  app_id: number;
  app_name: string | null;
}

// ─── RFQ & Marketplace ─────────────────────────────────────────────────────

export type RFQStatus = 'DRAFT' | 'PARSED' | 'MATCHED' | 'CONFIRMED';

export interface RFQ {
  id: string;
  raw_text: string;
  status: RFQStatus;
  parsed_fields: Record<string, string> | null;
  created_at: string;
}

export interface SellerMatch {
  enterprise_id: string;
  enterprise_name: string;
  score: number;
  rank: number;
}

// ─── Negotiation Sessions ──────────────────────────────────────────────────

export type SessionStatus = 'ACTIVE' | 'AGREED' | 'STALLED' | 'FAILED' | 'TERMINATED';

export interface NegotiationSession {
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

export interface NegotiationOffer {
  round: number;
  agent: 'BUYER' | 'SELLER';
  price: number;
  currency: string;
  terms: Record<string, string>;
  confidence: number;
  created_at: string;
}

// ─── Escrow ────────────────────────────────────────────────────────────────

export type EscrowStatus = 'DEPLOYED' | 'FUNDED' | 'RELEASED' | 'REFUNDED' | 'FROZEN';

export interface Escrow {
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

export interface Settlement {
  id: string;
  escrow_id: string;
  type: 'FUND' | 'RELEASE' | 'REFUND' | 'FREEZE';
  amount: number;
  tx_id: string;
  created_at: string;
}

export interface BuildFundTxnResponse {
  unsigned_transactions: string[];
  group_id: string;
  transaction_count: number;
  description: string;
}

export interface SubmitSignedFundResponse {
  txid: string;
  confirmed_round: number;
}

// ─── Compliance ────────────────────────────────────────────────────────────

export interface AuditLog {
  id: string;
  escrow_id: string;
  action: string;
  actor: string;
  hash: string;
  prev_hash: string;
  created_at: string;
}

// ─── API Response Envelope ─────────────────────────────────────────────────

export interface ApiResponse<T> {
  status: 'success' | 'error';
  data: T;
}
