-- Migration: Add property_watches table for Annual Assessment Monitor
-- Tracks properties that users want to monitor for assessment changes

CREATE TABLE IF NOT EXISTS property_watches (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    account_number TEXT NOT NULL,
    district TEXT NOT NULL DEFAULT 'HCAD',
    address TEXT,
    baseline_appraised NUMERIC,
    baseline_year INT,
    latest_appraised NUMERIC,
    latest_year INT,
    change_pct NUMERIC,
    alert_triggered BOOLEAN DEFAULT FALSE,
    alert_threshold_pct NUMERIC DEFAULT 5.0,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(account_number, district)
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_watches_account ON property_watches(account_number);
CREATE INDEX IF NOT EXISTS idx_watches_alert ON property_watches(alert_triggered) WHERE alert_triggered = TRUE;

-- RLS policies (if RLS is enabled)
ALTER TABLE property_watches ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all on property_watches" ON property_watches FOR ALL USING (true);
