-- Query to find the specific property by address
SELECT 
    account_number,
    address,
    neighborhood_code,
    building_area,
    appraised_value,
    district,
    property_type
FROM 
    properties
WHERE 
    address ILIKE '%935 Lamonte%';

-- Query to find it by the resolved account ID from the logs
SELECT 
    account_number,
    address,
    neighborhood_code,
    building_area,
    appraised_value,
    district,
    property_type
FROM 
    properties
WHERE 
    account_number = '0660460450034';

-- Query to find ALL properties on Lamonte Ln in the database
-- This helps us see if the other properties have the same neighborhood_code and building_area
SELECT 
    account_number,
    address,
    neighborhood_code,
    building_area,
    appraised_value,
    district
FROM 
    properties
WHERE 
    address ILIKE '%Lamonte%';
