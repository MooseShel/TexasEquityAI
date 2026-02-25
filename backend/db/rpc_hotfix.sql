-- Hotfix: Recreate the match_properties RPC function with matching data types
-- Postgres strict return typing requires the RETURN TABLE definitions to exactly match what the table returns.

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
  WHERE properties.district = p_district
    AND properties.embedding IS NOT NULL
  ORDER BY properties.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
