-- Migration: Add district support to properties table
-- Run this in your Supabase SQL Editor

-- 1. Add district column (defaults to HCAD for existing records)
ALTER TABLE public.properties 
ADD COLUMN IF NOT EXISTS district text DEFAULT 'HCAD';

-- 2. Add neighborhood_code if missing (crucial for new equity logic)
ALTER TABLE public.properties 
ADD COLUMN IF NOT EXISTS neighborhood_code text;

-- 3. Add market_value if missing (store live market data)
ALTER TABLE public.properties 
ADD COLUMN IF NOT EXISTS market_value numeric;

-- 4. Create index on district for faster filtering
CREATE INDEX IF NOT EXISTS idx_properties_district ON public.properties (district);
