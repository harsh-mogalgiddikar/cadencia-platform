-- Migration 006: Agent Memory — pgvector RAG storage
-- S3 Tenant Vault → Chunk → Embed → pgvector agent_memory table.
-- context.md §11: HNSW index for <50ms Top-5 cosine similarity queries.

-- ============================================================================
-- agent_memory: Chunked + embedded enterprise documents for RAG retrieval
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    role VARCHAR(10) NOT NULL DEFAULT 'buyer',
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_agent_memory_role CHECK (role IN ('buyer', 'seller'))
);

-- Tenant isolation index (WHERE tenant_id = ?)
CREATE INDEX IF NOT EXISTS ix_agent_memory_tenant_id
    ON agent_memory (tenant_id);

-- Composite index for role-scoped retrieval
CREATE INDEX IF NOT EXISTS ix_agent_memory_tenant_role
    ON agent_memory (tenant_id, role);

-- HNSW index for <50ms Top-5 cosine similarity queries.
-- vector_cosine_ops: normalized cosine distance for Gemini embeddings.
-- m=16, ef_construction=64 balances build speed vs recall.
CREATE INDEX IF NOT EXISTS agent_memory_hnsw
    ON agent_memory USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE agent_memory IS
    'pgvector-backed agent memory for RAG retrieval. '
    'Stores 512-token document chunks with 1536-dim Gemini embeddings. '
    'Tenant-isolated. Used by Layer 3 LLM advisory.';

COMMENT ON COLUMN agent_memory.embedding IS
    '1536-dimensional vector from Gemini text-embedding-004. '
    'Indexed with HNSW for sub-50ms cosine similarity search.';

COMMENT ON COLUMN agent_memory.metadata IS
    'JSONB: {source: s3_key, chunk_index, total_chunks, original_filename}';
