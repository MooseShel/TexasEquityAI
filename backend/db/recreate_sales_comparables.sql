DROP TABLE IF EXISTS sales_comparables;

CREATE TABLE sales_comparables (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_number TEXT NOT NULL,
    protest_id UUID, -- Optional, if we want to tie it to a specific protest run
    
    address TEXT NOT NULL,
    sale_price NUMERIC,
    sale_date DATE,
    sqft INTEGER,
    price_per_sqft NUMERIC,
    year_built INTEGER,
    source TEXT DEFAULT 'RentCast',
    dist_from_subject NUMERIC,
    similarity_score NUMERIC,
    property_type TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookup by the subject property
CREATE INDEX idx_sales_comparables_account ON sales_comparables(account_number);

-- Disable Row Level Security so the backend can freely insert and read comps
ALTER TABLE sales_comparables DISABLE ROW LEVEL SECURITY;
