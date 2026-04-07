-- Cadencia — Complete Database Schema
-- Generated from SQLAlchemy ORM models across all 6 bounded contexts.
-- Run AFTER init_db.sql (which creates pgvector + uuid-ossp extensions).
-- Idempotent: uses IF NOT EXISTS throughout.

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════════════
-- 1. IDENTITY — enterprises, users, api_keys
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS enterprises (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255)    NOT NULL,
    pan             VARCHAR(10)     NOT NULL,
    gstin           VARCHAR(15)     NOT NULL,
    kyc_status      VARCHAR(20)     NOT NULL DEFAULT 'PENDING',
    trade_role      VARCHAR(10)     NOT NULL,
    algorand_wallet VARCHAR(58),
    kyc_documents   JSONB,
    agent_config    JSONB,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_enterprises_pan   UNIQUE (pan),
    CONSTRAINT uq_enterprises_gstin UNIQUE (gstin),
    CONSTRAINT ck_enterprises_kyc_status CHECK (
        kyc_status IN ('PENDING','KYC_SUBMITTED','VERIFIED','ACTIVE')
    ),
    CONSTRAINT ck_enterprises_trade_role CHECK (
        trade_role IN ('BUYER','SELLER','BOTH')
    )
);

CREATE INDEX IF NOT EXISTS ix_enterprises_pan   ON enterprises (pan);
CREATE INDEX IF NOT EXISTS ix_enterprises_gstin ON enterprises (gstin);

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id   UUID            NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    email           VARCHAR(255)    NOT NULL,
    role            VARCHAR(30)     NOT NULL,
    password_hash   TEXT            NOT NULL,
    is_active       BOOLEAN         NOT NULL DEFAULT true,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_role CHECK (
        role IN ('ADMIN','BUYER','SELLER','COMPLIANCE_OFFICER','TREASURY_MANAGER','AUDITOR')
    )
);

CREATE INDEX IF NOT EXISTS ix_users_email         ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_enterprise_id ON users (enterprise_id);

CREATE TABLE IF NOT EXISTS api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id   UUID            NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    name            VARCHAR(100)    NOT NULL,
    key_hash        VARCHAR(64)     NOT NULL UNIQUE,
    is_active       BOOLEAN         NOT NULL DEFAULT true,
    expires_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_api_keys_key_hash UNIQUE (key_hash)
);

CREATE INDEX IF NOT EXISTS ix_api_keys_key_hash      ON api_keys (key_hash);
CREATE INDEX IF NOT EXISTS ix_api_keys_enterprise_id ON api_keys (enterprise_id);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 2. MARKETPLACE — rfqs, capability_profiles, matches
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS rfqs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    status              VARCHAR(20)     NOT NULL DEFAULT 'DRAFT',
    raw_text            TEXT,
    product_name        VARCHAR(255),
    hsn_code            VARCHAR(8),
    quantity            DOUBLE PRECISION,
    quantity_unit       VARCHAR(20),
    budget_min          DOUBLE PRECISION,
    budget_max          DOUBLE PRECISION,
    currency            VARCHAR(3)      NOT NULL DEFAULT 'INR',
    delivery_window_days INTEGER,
    geography           VARCHAR(100),
    parsed_fields       JSONB,
    embedding           vector(1536),
    confirmed_match_id  UUID,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT ck_rfqs_status CHECK (
        status IN ('DRAFT','PARSED','MATCHED','CONFIRMED','SETTLED')
    )
);

CREATE INDEX IF NOT EXISTS ix_rfqs_enterprise_id_status ON rfqs (enterprise_id, status);

CREATE TABLE IF NOT EXISTS capability_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    commodities         TEXT[],
    hsn_codes           TEXT[],
    min_order_value     DOUBLE PRECISION,
    max_order_value     DOUBLE PRECISION,
    geographies_served  TEXT[],
    lead_time_days      INTEGER,
    certifications      TEXT[],
    profile_text        TEXT,
    embedding           vector(1536),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_capability_profiles_enterprise_id UNIQUE (enterprise_id)
);

CREATE TABLE IF NOT EXISTS matches (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id                  UUID            NOT NULL REFERENCES rfqs(id) ON DELETE CASCADE,
    seller_enterprise_id    UUID            NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    score                   DOUBLE PRECISION NOT NULL,
    rank                    INTEGER         NOT NULL,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_matches_rfq_id               ON matches (rfq_id);
CREATE INDEX IF NOT EXISTS ix_matches_seller_enterprise_id  ON matches (seller_enterprise_id);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 3. NEGOTIATION — sessions, offers, agent_profiles, playbooks, opponent, memory
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS negotiation_sessions (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id                      UUID            NOT NULL,
    match_id                    UUID            NOT NULL,
    buyer_enterprise_id         UUID            NOT NULL REFERENCES enterprises(id),
    seller_enterprise_id        UUID            NOT NULL REFERENCES enterprises(id),
    status                      VARCHAR(20)     NOT NULL DEFAULT 'ACTIVE',
    current_round               INTEGER         NOT NULL DEFAULT 0,
    stall_threshold             INTEGER         NOT NULL DEFAULT 10,
    convergence_threshold_pct   DOUBLE PRECISION NOT NULL DEFAULT 2.0,
    agreed_price                NUMERIC(18,4),
    agreed_at                   TIMESTAMPTZ,
    completed_at                TIMESTAMPTZ,
    metadata                    JSONB,
    schema_failure_count        INTEGER         NOT NULL DEFAULT 0,
    stall_counter               INTEGER         NOT NULL DEFAULT 0,
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT ck_negotiation_sessions_status CHECK (
        status IN ('ACTIVE','AGREED','FAILED','EXPIRED','HUMAN_REVIEW',
                   'INIT','BUYER_ANCHOR','SELLER_RESPONSE','ROUND_LOOP',
                   'WALK_AWAY','STALLED','TIMEOUT','POLICY_BREACH')
    )
);

CREATE INDEX IF NOT EXISTS ix_negotiation_sessions_rfq_id               ON negotiation_sessions (rfq_id);
CREATE INDEX IF NOT EXISTS ix_negotiation_sessions_status               ON negotiation_sessions (status);
CREATE INDEX IF NOT EXISTS ix_negotiation_sessions_buyer_enterprise_id  ON negotiation_sessions (buyer_enterprise_id);

CREATE TABLE IF NOT EXISTS offers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID            NOT NULL REFERENCES negotiation_sessions(id) ON DELETE CASCADE,
    round_number        INTEGER         NOT NULL,
    proposer_role       VARCHAR(10)     NOT NULL,
    price               NUMERIC(18,4)   NOT NULL,
    confidence          DOUBLE PRECISION,
    reasoning           TEXT,
    is_human_override   BOOLEAN         NOT NULL DEFAULT false,
    raw_llm_output      JSONB,
    archived_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT ck_offers_proposer_role CHECK (
        proposer_role IN ('BUYER','SELLER','HUMAN')
    )
);

CREATE INDEX IF NOT EXISTS ix_offers_session_id_round_number ON offers (session_id, round_number);

CREATE TABLE IF NOT EXISTS agent_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    automation_level    VARCHAR(20)     NOT NULL DEFAULT 'SUPERVISED',
    risk_profile        JSONB,
    strategy_weights    JSONB,
    budget_ceiling      DOUBLE PRECISION,
    max_rounds          INTEGER         NOT NULL DEFAULT 10,
    history_embedding   vector(1536),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_agent_profiles_enterprise_id UNIQUE (enterprise_id),
    CONSTRAINT ck_agent_profiles_automation_level CHECK (
        automation_level IN ('FULLY_AUTONOMOUS','SUPERVISED','MANUAL')
    )
);

CREATE TABLE IF NOT EXISTS industry_playbooks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hsn_prefix      VARCHAR(8)      NOT NULL,
    industry_name   VARCHAR(100)    NOT NULL,
    playbook_text   TEXT            NOT NULL,
    strategy_hints  JSONB,
    is_active       BOOLEAN         NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_industry_playbooks_hsn_prefix ON industry_playbooks (hsn_prefix);

CREATE TABLE IF NOT EXISTS opponent_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    observer_id     UUID            NOT NULL,
    target_id       UUID            NOT NULL,
    flexibility     DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    belief          JSONB,
    rounds_observed INTEGER         NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_opponent_profiles_observer_target
    ON opponent_profiles (observer_id, target_id);
CREATE INDEX IF NOT EXISTS ix_opponent_profiles_target_id
    ON opponent_profiles (target_id);

CREATE TABLE IF NOT EXISTS agent_memory (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID            NOT NULL,
    role        VARCHAR(10)     NOT NULL DEFAULT 'buyer',
    content     TEXT            NOT NULL,
    embedding   vector(1536),
    metadata    JSONB,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_agent_memory_tenant_id   ON agent_memory (tenant_id);
CREATE INDEX IF NOT EXISTS ix_agent_memory_tenant_role ON agent_memory (tenant_id, role);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 4. SETTLEMENT — escrow_contracts, settlements
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS escrow_contracts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id              UUID            NOT NULL REFERENCES negotiation_sessions(id),
    algo_app_id             BIGINT UNIQUE,
    amount_microalgo        BIGINT          NOT NULL,
    buyer_algorand_address  VARCHAR(58)     NOT NULL,
    seller_algorand_address VARCHAR(58)     NOT NULL,
    status                  VARCHAR(20)     NOT NULL DEFAULT 'DEPLOYED',
    is_frozen               BOOLEAN         NOT NULL DEFAULT false,
    deploy_tx_id            VARCHAR(52),
    fund_tx_id              VARCHAR(52),
    release_tx_id           VARCHAR(52),
    refund_tx_id            VARCHAR(52),
    merkle_root             VARCHAR(64),
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_escrow_contracts_session_id  UNIQUE (session_id),
    CONSTRAINT uq_escrow_contracts_algo_app_id UNIQUE (algo_app_id),
    CONSTRAINT ck_escrow_contracts_status CHECK (
        status IN ('DEPLOYED','FUNDED','RELEASED','REFUNDED')
    )
);

CREATE INDEX IF NOT EXISTS ix_escrow_contracts_session_id  ON escrow_contracts (session_id);
CREATE INDEX IF NOT EXISTS ix_escrow_contracts_algo_app_id ON escrow_contracts (algo_app_id);

CREATE TABLE IF NOT EXISTS settlements (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    escrow_id           UUID            NOT NULL REFERENCES escrow_contracts(id),
    milestone_index     INTEGER         NOT NULL,
    amount_microalgo    BIGINT          NOT NULL,
    tx_id               VARCHAR(52),
    oracle_confirmation JSONB,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_settlements_escrow_id ON settlements (escrow_id);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 5. COMPLIANCE — audit_entries, fema_records, gst_records, export_jobs
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS audit_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    escrow_id       UUID            NOT NULL,
    sequence_no     INTEGER         NOT NULL,
    event_type      VARCHAR(100)    NOT NULL,
    payload_json    TEXT            NOT NULL,
    prev_hash       VARCHAR(64)     NOT NULL,
    entry_hash      VARCHAR(64)     NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_audit_entries_escrow_seq UNIQUE (escrow_id, sequence_no)
);

CREATE INDEX IF NOT EXISTS ix_audit_entries_escrow_created
    ON audit_entries (escrow_id, created_at);

CREATE TABLE IF NOT EXISTS fema_records (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    escrow_id               UUID            NOT NULL UNIQUE,
    form_type               VARCHAR(4)      NOT NULL,
    purpose_code            VARCHAR(6)      NOT NULL,
    buyer_pan               VARCHAR(10)     NOT NULL,
    seller_pan              VARCHAR(10)     NOT NULL,
    amount_inr              NUMERIC(20,2)   NOT NULL,
    amount_algo             NUMERIC(20,6)   NOT NULL,
    fx_rate_inr_per_algo    NUMERIC(20,6)   NOT NULL,
    merkle_root             VARCHAR(64)     NOT NULL,
    generated_at            TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_fema_records_escrow_id ON fema_records (escrow_id);

CREATE TABLE IF NOT EXISTS gst_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    escrow_id       UUID            NOT NULL UNIQUE,
    hsn_code        VARCHAR(8)      NOT NULL,
    buyer_gstin     VARCHAR(15)     NOT NULL,
    seller_gstin    VARCHAR(15)     NOT NULL,
    tax_type        VARCHAR(10)     NOT NULL,
    taxable_amount  NUMERIC(20,2)   NOT NULL,
    igst_amount     NUMERIC(20,2)   NOT NULL,
    cgst_amount     NUMERIC(20,2)   NOT NULL,
    sgst_amount     NUMERIC(20,2)   NOT NULL,
    generated_at    TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_gst_records_escrow_id ON gst_records (escrow_id);

CREATE TABLE IF NOT EXISTS export_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    escrow_ids      JSONB           NOT NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'PENDING',
    redis_key       VARCHAR(200),
    error_message   TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,

    CONSTRAINT ck_export_jobs_status CHECK (
        status IN ('PENDING','DONE','FAILED')
    )
);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 6. TREASURY — liquidity_pools, fx_positions
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS liquidity_pools (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id           UUID            NOT NULL REFERENCES enterprises(id) UNIQUE,
    inr_balance             NUMERIC(18,2)   NOT NULL DEFAULT 0,
    usdc_balance            NUMERIC(18,6)   NOT NULL DEFAULT 0,
    algo_balance_microalgo  BIGINT          NOT NULL DEFAULT 0,
    last_fx_rate_inr_usd    NUMERIC(18,8)   NOT NULL DEFAULT 0,
    last_rate_updated_at    TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT ck_liquidity_pools_inr_non_negative   CHECK (inr_balance >= 0),
    CONSTRAINT ck_liquidity_pools_usdc_non_negative  CHECK (usdc_balance >= 0),
    CONSTRAINT ck_liquidity_pools_algo_non_negative  CHECK (algo_balance_microalgo >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_liquidity_pools_enterprise_id
    ON liquidity_pools (enterprise_id);

CREATE TABLE IF NOT EXISTS fx_positions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id   UUID            NOT NULL REFERENCES enterprises(id),
    currency_pair   VARCHAR(10)     NOT NULL,
    direction       VARCHAR(5)      NOT NULL,
    notional_amount NUMERIC(18,2)   NOT NULL,
    entry_rate      NUMERIC(18,8)   NOT NULL,
    current_rate    NUMERIC(18,8)   NOT NULL,
    status          VARCHAR(10)     NOT NULL DEFAULT 'OPEN',
    closed_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT ck_fx_positions_direction CHECK (direction IN ('LONG','SHORT')),
    CONSTRAINT ck_fx_positions_status    CHECK (status IN ('OPEN','CLOSED'))
);

CREATE INDEX IF NOT EXISTS ix_fx_positions_enterprise_id ON fx_positions (enterprise_id);
CREATE INDEX IF NOT EXISTS ix_fx_positions_status        ON fx_positions (status);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 7. VECTOR INDEXES (pgvector — created after tables)
-- ═══════════════════════════════════════════════════════════════════════════════

-- RFQ embedding HNSW index (context.md §11: m=16, ef_construction=64)
CREATE INDEX IF NOT EXISTS ix_rfqs_embedding_hnsw
    ON rfqs USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Capability profile IVFFlat index (context.md §11: lists=100, cosine distance)
CREATE INDEX IF NOT EXISTS ix_capability_profiles_embedding_ivfflat
    ON capability_profiles USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Agent memory HNSW index (<50ms Top-5 cosine similarity)
CREATE INDEX IF NOT EXISTS ix_agent_memory_embedding_hnsw
    ON agent_memory USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Agent profile history embedding HNSW index
CREATE INDEX IF NOT EXISTS ix_agent_profiles_history_embedding_hnsw
    ON agent_profiles USING hnsw (history_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 8. UPDATE TRIGGER — auto-set updated_at on UPDATE
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN
        SELECT unnest(ARRAY[
            'enterprises', 'users', 'rfqs', 'capability_profiles',
            'negotiation_sessions', 'offers', 'agent_profiles', 'industry_playbooks',
            'opponent_profiles', 'escrow_contracts', 'fema_records', 'gst_records',
            'liquidity_pools', 'fx_positions'
        ])
    LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_%s_updated_at ON %I; '
            'CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();',
            tbl, tbl, tbl, tbl
        );
    END LOOP;
END $$;

COMMIT;
