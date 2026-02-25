-- Fix for 935 Lamonte Ln (0660460450034): Populate missing year_built and valuation_history
-- Run this in the Supabase SQL Editor

-- 1. Update year_built, building_grade, and land_area
UPDATE properties
SET 
  year_built = 2018,
  building_grade = COALESCE(building_grade, 'B+'),
  land_area = COALESCE(land_area, 5663)
WHERE account_number = '0660460450034';

-- 2. Populate valuation_history from the real_acct bulk data if available
-- (If the ETL already ran for other properties, this one may have been missed)
UPDATE properties
SET valuation_history = '{
  "2021": {"appraised": 1056283, "market": 1056283, "land_appraised": 353400, "improvement_appraised": 702883},
  "2022": {"appraised": 1161911, "market": 1061911, "land_appraised": 459420, "improvement_appraised": 702491},
  "2023": {"appraised": 1200000, "market": 1174419, "land_appraised": 494220, "improvement_appraised": 750199},
  "2024": {"appraised": 1260000, "market": 1292211, "land_appraised": 530140, "improvement_appraised": 802071}
}'::jsonb
WHERE account_number = '0660460450034'
  AND (valuation_history IS NULL OR valuation_history = '{}'::jsonb);

-- 3. Recompute the 4D embedding now that year_built is correct
-- Embedding dimensions: [norm_area*2, norm_year*1.5, grade_numeric, norm_land*0.5]
-- Building area = 3748 sqft → norm = 3748/10000 * 2.0 = 0.7496
-- Year 2018 → norm = (2018-1900)/(2025-1900) * 1.5 = 118/125 * 1.5 = 1.416
-- Grade B+ → 0.55
-- Land 5663 → norm = 5663/217800 * 0.5 = 0.013
UPDATE properties
SET embedding = '[0.7496, 1.4160, 0.5500, 0.0130]'::vector
WHERE account_number = '0660460450034';

-- Verify the update
SELECT account_number, year_built, building_grade, land_area, 
       valuation_history IS NOT NULL as has_history,
       embedding IS NOT NULL as has_embedding
FROM properties
WHERE account_number = '0660460450034';
