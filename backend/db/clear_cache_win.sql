-- 1. Clear all generated protest packets and their data
DELETE FROM protests;

-- 2. Clear all cached JSON blobs on the main properties table
-- This forces the system to re-run the equity agent, sales agent, vision agent, etc.
UPDATE properties 
SET 
  cached_comps = NULL,
  comps_scraped_at = NULL,
  sales_comps_cache = NULL,
  sales_comps_scraped_at = NULL,
  vision_cache = NULL,
  vision_scraped_at = NULL;

-- 3. Clear the individual comparable tables
-- These tables store the structured history of which comps were selected,
-- but the main app primarily reads from the JSON caches above for speed.
DELETE FROM equity_comparables;
DELETE FROM sales_comparables;
