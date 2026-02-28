-- This script deletes all property records where the address is missing (NULL).
-- It will free up database storage and improve vector search performance.

-- WARNING: This action cannot be undone. You may want to run a SELECT count(*) first 
-- to verify exactly how many rows will be deleted.
-- Example: SELECT count(*) FROM public.properties WHERE address IS NULL;

DELETE FROM public.properties 
WHERE address IS NULL;

-- If you also want to delete records with empty string addresses, uncomment this:
-- DELETE FROM public.properties WHERE address = '';

-- If you eventually want to delete records with null neighborhood codes as well:
-- DELETE FROM public.properties WHERE neighborhood_code IS NULL;
