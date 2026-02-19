-- IMPORTANT: Run these statements ONE BY ONE in the SQL Editor to avoid timeouts.
-- The 'properties' table has ~3.5M rows, so creating multiple indexes at once will time out.

-- 1. Create Core Indexes (Run this block first)
CREATE INDEX IF NOT EXISTS idx_properties_district ON properties(district);
-- Wait for success...

-- 2. Create Neighborhood Index (Critical for the 500 error)
CREATE INDEX IF NOT EXISTS idx_properties_neighborhood_code ON properties(neighborhood_code);
-- Wait for success...

-- 3. Create Value Filtering Index
CREATE INDEX IF NOT EXISTS idx_properties_appraised_value ON properties(appraised_value);
-- Wait for success...

-- 4. Create Range Query Indexes (Optional but good)
CREATE INDEX IF NOT EXISTS idx_properties_building_area ON properties(building_area);
CREATE INDEX IF NOT EXISTS idx_properties_year_built ON properties(year_built);
-- Wait for success...

-- 5. HEAVY OPERATION: Create Trigram Extension & Index for Address Search
-- This may take several minutes. If it times out in the dashboard, you might need to run it via CLI or ignore it (Layer 2.5 relies on this).
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_properties_address_trigram ON properties USING gist (address gist_trgm_ops);
