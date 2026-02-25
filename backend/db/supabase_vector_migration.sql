-- Migration: Enable pgvector and add embedding column for Equity AI similarities

-- 1. Enable the pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Add the embedding column to the properties table
-- We use a 4-dimensional vector to encode physical similarities:
-- [Normalized Area, Normalized Year Built, Normalized Grade, Normalized Land Area]
-- e.g., vector(4)
ALTER TABLE properties ADD COLUMN IF NOT EXISTS embedding vector(4);

-- 3. Create a performance index for fast cosine/L2 distance search
-- An HNSW index is typically recommended for pgvector
CREATE INDEX ON properties USING hnsw (embedding vector_l2_ops);

-- Note: The Python application will now handle computing the 4D vectors 
-- and updating this column.

-- 4. Create an RPC function to perform the vector similarity search
-- This allows the Python backend to simply call supabase.rpc('match_properties')
CREATE OR REPLACE FUNCTION match_properties (
  query_embedding vector(4),
  match_threshold float,
  match_count int,
  p_district text
) RETURNS TABLE (
  account_number text,
  address text,
  appraised_value numeric,
  building_area numeric,
  year_built int,
  building_grade text,
  land_area numeric,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    properties.account_number,
    properties.address,
    properties.appraised_value,
    properties.building_area,
    properties.year_built,
    properties.building_grade,
    properties.land_area,
    1 - (properties.embedding <=> query_embedding) AS similarity
  FROM properties
  WHERE properties.district = p_district
    AND properties.embedding IS NOT NULL
    AND 1 - (properties.embedding <=> query_embedding) > match_threshold
  ORDER BY properties.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
