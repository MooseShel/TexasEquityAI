-- Migration 005: Add state_class column for property type classification
-- HCAD state class codes: A1=Residential, F1=Commercial, B1=Mobile, C1=Vacant, etc.
ALTER TABLE properties ADD COLUMN IF NOT EXISTS state_class TEXT;

-- Index for fast filtering by property type
CREATE INDEX IF NOT EXISTS idx_properties_state_class ON properties (state_class);
