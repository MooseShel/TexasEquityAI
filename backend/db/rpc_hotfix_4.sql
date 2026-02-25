-- Hotfix 4: The Operator fix

-- I realized the core problem! I created the HNSW index using `vector_l2_ops` 
-- which optimizes Euclidean distance (`<->`).
-- But my previous scripts used (`<=>`) which is Cosine distance!
-- Because the operator operators didn't match, Postgres ignored the index completely.

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
    -- Using <-> for L2 Euclidean Distance. 
    -- We invert it for "similarity" score (0 = perfectly identical, larger = more different)
    -- so similarity = 1 - distance, but L2 distance can be > 1.
    -- We'll just return the exact L2 distance as the "similarity" column for now 
    -- and the Python script can format it.
    (properties.embedding <-> query_embedding)::float8 AS similarity
  FROM properties
  -- We can restore the district filter now since the index will actually work!
  WHERE properties.district = p_district
    AND properties.embedding IS NOT NULL
  ORDER BY properties.embedding <-> query_embedding
  LIMIT match_count;
END;
$$;
