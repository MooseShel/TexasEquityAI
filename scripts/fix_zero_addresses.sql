-- ============================================================
-- Clean up "0 " prefix addresses (vacant/unaddressed parcels)
-- Run ONE district at a time to avoid timeout on 2M+ row table
-- ============================================================

-- Step 1: Preview count per district (run first)
-- SELECT district, COUNT(*) FROM properties
-- WHERE address LIKE '0 %' AND district IN ('HCAD','DCAD','TAD','CCAD')
-- GROUP BY district;

-- Step 2: Fix HCAD
UPDATE properties
SET address = SUBSTRING(address FROM 3)
WHERE district = 'HCAD'
  AND address ~ '^0 [A-Za-z]';

-- Step 3: Fix DCAD (run after HCAD completes)
UPDATE properties
SET address = SUBSTRING(address FROM 3)
WHERE district = 'DCAD'
  AND address ~ '^0 [A-Za-z]';

-- Step 4: Fix TAD (run after DCAD completes)
UPDATE properties
SET address = SUBSTRING(address FROM 3)
WHERE district = 'TAD'
  AND address ~ '^0 [A-Za-z]';

-- Step 5: Fix CCAD (run after TAD completes)
UPDATE properties
SET address = SUBSTRING(address FROM 3)
WHERE district = 'CCAD'
  AND address ~ '^0 [A-Za-z]';

-- Verify: should return 0 rows when done
-- SELECT COUNT(*) FROM properties WHERE address ~ '^0 [A-Za-z]';

