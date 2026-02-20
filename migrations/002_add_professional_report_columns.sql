-- Migration 002: Add Professional Report Fields
-- Adds columns for building grade, quality, valuation history, and land breakdowns.

ALTER TABLE properties 
ADD COLUMN IF NOT EXISTS land_area NUMERIC,
ADD COLUMN IF NOT EXISTS building_grade TEXT,
ADD COLUMN IF NOT EXISTS building_quality TEXT,
ADD COLUMN IF NOT EXISTS valuation_history JSONB,
ADD COLUMN IF NOT EXISTS land_breakdown JSONB;

-- Comment for documentation
COMMENT ON COLUMN properties.valuation_history IS 'JSONB object containing year-by-year prelim vs final value breakdowns';
COMMENT ON COLUMN properties.land_breakdown IS 'JSONB object containing sf1 (primary) and sf3 (residual) land details';
