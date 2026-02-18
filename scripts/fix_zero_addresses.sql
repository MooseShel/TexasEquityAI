-- ============================================================
-- Clean up "0 " prefix addresses in properties table
-- These come from vacant lots / unaddressed parcels where
-- the street number is 0 (e.g. "0 BOUDREAUX RD, TOMBALL, TX")
-- ============================================================

-- Option A (recommended): Strip the leading "0 " so address becomes usable
-- e.g. "0 BOUDREAUX RD, TOMBALL, TX, 77375" → "BOUDREAUX RD, TOMBALL, TX, 77375"
UPDATE properties
SET address = SUBSTRING(address FROM 3)   -- remove first two chars "0 "
WHERE address ~ '^0 [A-Za-z]';            -- starts with "0 " followed by a letter

-- Check how many rows were affected (run separately to preview before applying):
-- SELECT COUNT(*) FROM properties WHERE address ~ '^0 [A-Za-z]';

-- ============================================================
-- Option B: Null out the address entirely for these parcels
-- (uncomment below if you prefer to remove rather than fix)
-- ============================================================
-- UPDATE properties
-- SET address = NULL
-- WHERE address ~ '^0 [A-Za-z]';

-- ============================================================
-- Verify result after running Option A:
-- ============================================================
-- SELECT account_number, address, district
-- FROM properties
-- WHERE address ~ '^0 [A-Za-z]'
-- LIMIT 10;
-- (should return 0 rows after cleanup)
