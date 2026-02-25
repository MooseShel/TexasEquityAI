-- Hotfix 3: The absolute purest vector search
-- It turns out HNSW indexes on pgvector will completely fail to be used if there is *any* WHERE clause.
-- We must remove `IS NOT NULL` as well.

DROP FUNCTION IF EXISTS match_properties(vector(4), float, int, text);

CREATE OR REPLACE FUNCTION match_properties (
  query_embedding vector(4),
  match_threshold float,
  match_count int,
  p_district text
) RETURNS TABLE (
  account_number text,
  address text,
  appraised_value float8,
  building_area float8,
  year_built int,
  building_grade text,
  land_area float8,
  similarity float8
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    properties.account_number,
    properties.address,
    properties.appraised_value::float8,
    properties.building_area::float8,
    properties.year_built,
    properties.building_grade,
    properties.land_area::float8,
    (1 - (properties.embedding <=> query_embedding))::float8 AS similarity
  FROM properties
  -- NO WHERE CLAUSE AT ALL. This guarantees HNSW index usage.
  -- Null embeddings naturally bubble to the bottom of the distance search.
  ORDER BY properties.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
