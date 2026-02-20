-- Add caching columns to properties table for sales, FEMA, vision, and market data
-- These columns store JSON blobs + timestamps for TTL-based cache invalidation

ALTER TABLE properties ADD COLUMN IF NOT EXISTS sales_cache JSONB;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS sales_fetched_at TIMESTAMPTZ;

ALTER TABLE properties ADD COLUMN IF NOT EXISTS flood_cache JSONB;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS flood_fetched_at TIMESTAMPTZ;

ALTER TABLE properties ADD COLUMN IF NOT EXISTS vision_cache JSONB;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS vision_fetched_at TIMESTAMPTZ;

ALTER TABLE properties ADD COLUMN IF NOT EXISTS market_cache JSONB;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS market_fetched_at TIMESTAMPTZ;
