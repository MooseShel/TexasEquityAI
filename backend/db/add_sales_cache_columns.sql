-- Add caching columns for Sales Comparables to the main properties table
ALTER TABLE properties
ADD COLUMN IF NOT EXISTS sales_cache JSONB,
ADD COLUMN IF NOT EXISTS sales_fetched_at TIMESTAMPTZ;

-- (Optional) If we want a separate table in the future for analytics, 
-- but currently the backend just caches the JSON blob in 'properties'. 
