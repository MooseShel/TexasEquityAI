-- Hotfix 2: The absolute simplest vector search
-- Removing all WHERE clauses (except non-null) to encourage the planner
-- to use the HNSW index on the 1000 backfilled rows instead of Seq Scanning 1.3M rows.

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
  -- We set enable_seqscan to off for the duration of this function
  -- to force the query planner to use our HNSW index. 
  -- (Since the table is 99.9% null embeddings right now, Postgres thinks seq scan is faster)
  SET LOCAL enable_seqscan = off;

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
  -- No district filter right now, just raw vector proximity
  WHERE properties.embedding IS NOT NULL
  ORDER BY properties.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
