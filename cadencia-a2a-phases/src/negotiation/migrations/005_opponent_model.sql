-- Migration 005: Bayesian Opponent Model + DANP State Machine Extensions
-- Adds opponent_profiles table for persistent Bayesian beliefs
-- Adds DANP FSM tracking columns to negotiation_sessions

-- ============================================================================
-- opponent_profiles: Persistent Bayesian opponent belief profiles
-- ============================================================================

CREATE TABLE IF NOT EXISTS opponent_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    observer_id UUID NOT NULL,
    target_id UUID NOT NULL,
    flexibility DECIMAL NOT NULL DEFAULT 0.5,
    belief JSONB,  -- {"cooperative":0.25, "strategic":0.25, "stubborn":0.25, "bluffing":0.25}
    rounds_observed INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Unique index: one profile per (observer, target) pair
CREATE UNIQUE INDEX IF NOT EXISTS ix_opponent_profiles_observer_target
    ON opponent_profiles (observer_id, target_id);

-- Index for looking up all profiles targeting a specific entity
CREATE INDEX IF NOT EXISTS ix_opponent_profiles_target_id
    ON opponent_profiles (target_id);

-- ============================================================================
-- DANP FSM extensions to negotiation_sessions
-- ============================================================================

-- Add schema failure counter (3x failure → POLICY_BREACH)
ALTER TABLE negotiation_sessions
    ADD COLUMN IF NOT EXISTS schema_failure_count INT NOT NULL DEFAULT 0;

-- Add stall counter (consecutive rounds without concession)
ALTER TABLE negotiation_sessions
    ADD COLUMN IF NOT EXISTS stall_counter INT NOT NULL DEFAULT 0;

-- Update status check constraint to include DANP states
ALTER TABLE negotiation_sessions
    DROP CONSTRAINT IF EXISTS ck_negotiation_sessions_status;

ALTER TABLE negotiation_sessions
    ADD CONSTRAINT ck_negotiation_sessions_status
    CHECK (status IN (
        'ACTIVE', 'AGREED', 'FAILED', 'EXPIRED', 'HUMAN_REVIEW',
        'INIT', 'BUYER_ANCHOR', 'SELLER_RESPONSE', 'ROUND_LOOP',
        'WALK_AWAY', 'STALLED', 'TIMEOUT', 'POLICY_BREACH'
    ));
