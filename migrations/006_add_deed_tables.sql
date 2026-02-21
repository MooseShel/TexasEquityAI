-- Migration 006: Add deed data tables and sale recency columns
-- Source: HCAD deeds.txt (2.4M deed transfer records)

-- ── 1. Create property_deeds table ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS property_deeds (
    id BIGSERIAL PRIMARY KEY,
    acct TEXT NOT NULL,
    date_of_sale DATE,
    clerk_year INTEGER,
    clerk_id TEXT,
    deed_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(acct, deed_id)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_deeds_acct ON property_deeds (acct);
CREATE INDEX IF NOT EXISTS idx_deeds_date ON property_deeds (date_of_sale DESC);

-- ── 2. Add sale recency columns to properties table ─────────────────────
ALTER TABLE properties ADD COLUMN IF NOT EXISTS last_sale_date DATE;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS deed_count INTEGER DEFAULT 0;

-- Index for sale recency queries
CREATE INDEX IF NOT EXISTS idx_properties_last_sale ON properties (last_sale_date DESC);
