-- Hotfix: Add an HNSW index on the embedding column
-- Without this index, pgvector performs an exact nearest neighbor search (sequential scan)
-- across all rows, which causes a "statement timeout" on large tables.

-- First, set the work_mem higher just for this session to speed up index building
SET work_mem = '256MB';

-- Create the HNSW index for L2 distance (euclidean) which we use in the python script.
-- Note: Supabase limits index creation time. If this times out in the UI, you may need to
-- run it via the psql command line tool.
CREATE INDEX IF NOT EXISTS properties_embedding_idx 
ON properties 
USING hnsw (embedding vector_l2_ops)
WITH (m = 16, ef_construction = 64);

