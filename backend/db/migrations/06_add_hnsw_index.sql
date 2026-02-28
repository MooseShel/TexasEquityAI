-- Add HNSW Index to properties table for vector embeddings

-- pgvector recommends executing this mapping first for performance
SET maintenance_work_mem TO '2GB';

-- Create the HNSW index on the embedding column using the L2 Distance algorithm.
-- HNSW is much faster for queries but slightly slower for inserts than IVFFlat.
CREATE INDEX CONCURRENTLY IF NOT EXISTS properties_embedding_hnsw_idx 
ON properties 
USING hnsw (embedding vector_l2_ops)
WITH (m = 16, ef_construction = 64);
