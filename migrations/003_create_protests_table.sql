-- Migration 003: Create OR Update Protests and Equity Comparables Tables
-- Updated to handle cases where table exists but columns are missing.

-- 1. Create 'protests' table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.protests (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- 2. Add columns if they don't exist (idempotent)
ALTER TABLE public.protests ADD COLUMN IF NOT EXISTS account_number TEXT;
ALTER TABLE public.protests ADD COLUMN IF NOT EXISTS property_data JSONB;
ALTER TABLE public.protests ADD COLUMN IF NOT EXISTS equity_data JSONB;
ALTER TABLE public.protests ADD COLUMN IF NOT EXISTS vision_data JSONB;
ALTER TABLE public.protests ADD COLUMN IF NOT EXISTS narrative TEXT;
ALTER TABLE public.protests ADD COLUMN IF NOT EXISTS market_value NUMERIC;
ALTER TABLE public.protests ADD COLUMN IF NOT EXISTS pdf_url TEXT;

-- 3. Create 'equity_comparables' table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.equity_comparables (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- 4. Add columns to 'equity_comparables'
ALTER TABLE public.equity_comparables ADD COLUMN IF NOT EXISTS protest_id TEXT;
ALTER TABLE public.equity_comparables ADD COLUMN IF NOT EXISTS account_number TEXT;
ALTER TABLE public.equity_comparables ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE public.equity_comparables ADD COLUMN IF NOT EXISTS owner_name TEXT;
ALTER TABLE public.equity_comparables ADD COLUMN IF NOT EXISTS distance NUMERIC;
ALTER TABLE public.equity_comparables ADD COLUMN IF NOT EXISTS similarity NUMERIC;
ALTER TABLE public.equity_comparables ADD COLUMN IF NOT EXISTS appraised_val NUMERIC;
ALTER TABLE public.equity_comparables ADD COLUMN IF NOT EXISTS market_val NUMERIC;
ALTER TABLE public.equity_comparables ADD COLUMN IF NOT EXISTS sqft NUMERIC;
ALTER TABLE public.equity_comparables ADD COLUMN IF NOT EXISTS year_built INT;
ALTER TABLE public.equity_comparables ADD COLUMN IF NOT EXISTS grade TEXT;
ALTER TABLE public.equity_comparables ADD COLUMN IF NOT EXISTS cdu TEXT;

-- 5. Indexes
CREATE INDEX IF NOT EXISTS idx_protests_account ON public.protests (account_number);

-- 6. Row Level Security Policies
ALTER TABLE public.protests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.equity_comparables ENABLE ROW LEVEL SECURITY;

-- Reset policies to ensure they are correct
DROP POLICY IF EXISTS "Public Read Protests" ON public.protests;
DROP POLICY IF EXISTS "Public Insert Protests" ON public.protests;
DROP POLICY IF EXISTS "Public Read Comps" ON public.equity_comparables;
DROP POLICY IF EXISTS "Public Insert Comps" ON public.equity_comparables;

CREATE POLICY "Public Read Protests" ON public.protests FOR SELECT USING (true);
CREATE POLICY "Public Insert Protests" ON public.protests FOR INSERT WITH CHECK (true);
CREATE POLICY "Public Read Comps" ON public.equity_comparables FOR SELECT USING (true);
CREATE POLICY "Public Insert Comps" ON public.equity_comparables FOR INSERT WITH CHECK (true);
