import re
import logging

logger = logging.getLogger(__name__)

def is_real_address(address: str) -> bool:
    """
    Detects if an address is a placeholder/dummy.
    Returns True if the address seems valid, False otherwise.
    """
    if not address:
        return False
        
    placeholders = ["HCAD Account", "Example St", "Placeholder", "00000"]
    # Check for placeholder strings
    if any(p in address for p in placeholders):
        return False
        
    # Check if it's just an account number (digits only or digits with spaces)
    # We want street addresses, not account numbers here usually
    # But sometimes account numbers are passed as address? 
    # The original logic was:
    # return address and not any(p in address for p in placeholders)
    
    return True

def normalize_address(address: str, district: str = "HCAD") -> str:
    """
    Normalizes an address string:
    1. Removes 'HCAD Account' prefix.
    2. Appends City/State if missing based on district.
    3. Cleans up redundancy.
    """
    if not address:
        return ""
    
    cleaned = address.strip()
    
    # 1. Remove "HCAD Account" prefix
    cleaned = re.sub(r'(?i)HCAD\s*Account', '', cleaned).strip()
    
    # Remove leading non-alphanumeric chars
    while cleaned and not cleaned[0].isalnum():
        cleaned = cleaned[1:].strip()
        
    # 2. Smart City Append based on District
    # Definition of "has city" is rough, but looking for the specific city name is safer
    district_map = {
        "HCAD": "Houston, TX",
        "TCAD": "Austin, TX",
        "DCAD": "Dallas, TX",
        "CCAD": "Plano, TX",
        "TAD": "Fort Worth, TX"
    }
    
    target_city = district_map.get(district, "Houston, TX")
    short_city = target_city.split(",")[0] # e.g. "Dallas"
    
    # Check if the address already contains the city (e.g. "Dallas" or "Dallas, TX")
    # Case insensitive check
    if short_city.lower() not in cleaned.lower():
        # Special case: Don't append if it already has a DIFFERENT known city? 
        # For now, just append if missing.
        if not cleaned.endswith(target_city):
             cleaned = f"{cleaned}, {target_city}"
             
    # 3. Fix double occurrences "Houston, TX, Houston, TX"
    # A simple replacement for the specific city
    double_pattern = f", {target_city}, {target_city}"
    if double_pattern in cleaned:
        cleaned = cleaned.replace(double_pattern, f", {target_city}")
        
    return cleaned
