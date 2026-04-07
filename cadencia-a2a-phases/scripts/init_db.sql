-- Enable pgvector extension on container startup.
-- context.md §11: pgvector 0.7+ required for vector similarity search.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
