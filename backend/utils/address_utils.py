import re
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

def is_real_address(address: str) -> bool:
    """
    Detects if an address is a placeholder/dummy or an account number masquerading as an address.
    Returns True if the address seems like a real street address, False otherwise.
    """
    if not address:
        return False
        
    placeholders = ["HCAD Account", "Example St", "Placeholder", "00000"]
    if any(p in address for p in placeholders):
        return False
    
    # Reject if the first token (before any comma or space) is all digits
    # e.g. "0660460450034, Texas, Houston, TX" — account number used as address
    first_token = address.split(",")[0].strip().split()[0] if address.strip() else ""
    if first_token.isdigit() and len(first_token) >= 8:
        return False
    
    # Must contain at least one alphabetic word (street name)
    if not any(c.isalpha() for c in address):
        return False
        
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


# ── Directional and suffix expansion maps ──────────────────────────────────
_DIR_ABBR = {
    r'\bN\b': 'North', r'\bS\b': 'South', r'\bE\b': 'East', r'\bW\b': 'West',
    r'\bNE\b': 'Northeast', r'\bNW\b': 'Northwest',
    r'\bSE\b': 'Southeast', r'\bSW\b': 'Southwest',
}
_SUFFIX_ABBR = {
    r'\bSt\.?\b': 'Street', r'\bAve\.?\b': 'Avenue', r'\bBlvd\.?\b': 'Boulevard',
    r'\bDr\.?\b': 'Drive', r'\bLn\.?\b': 'Lane', r'\bRd\.?\b': 'Road',
    r'\bCt\.?\b': 'Court', r'\bPl\.?\b': 'Place', r'\bPkwy\.?\b': 'Parkway',
    r'\bFwy\.?\b': 'Freeway', r'\bHwy\.?\b': 'Highway', r'\bCir\.?\b': 'Circle',
    r'\bTrl\.?\b': 'Trail', r'\bSq\.?\b': 'Square',
}
# Strip unit/suite/apt suffixes (e.g. "# 5", "Suite 100", "Apt B", "Ste 3")
_UNIT_PATTERN = re.compile(
    r'\s*[,]?\s*(#|Suite|Ste|Apt|Apartment|Unit|Floor|Fl|Bldg|Building)\s*[\w-]*',
    re.IGNORECASE
)


def normalize_address_for_search(raw: str) -> str:
    """
    Normalizes a raw user-typed address for consistent API lookup:
    1. Strip unit/suite/apt suffixes
    2. Expand directional abbreviations (N → North, S → South, etc.)
    3. Expand street-type abbreviations (St → Street, Ave → Avenue, etc.)
    4. Collapse whitespace

    Used BEFORE sending to Supabase, RentCast, or RealEstateAPI so all
    three layers compare against the same normalized string.
    """
    if not raw:
        return ''
    s = raw.strip()

    # 1. Strip unit suffixes — must come first before we touch the street name
    s = _UNIT_PATTERN.sub('', s).strip().rstrip(',')

    # Split at comma to expand only the street part (preserve city/state/zip)
    parts = s.split(',', 1)
    street = parts[0].strip()
    rest = parts[1].strip() if len(parts) > 1 else ''

    # 2. Expand directional abbreviations on the street part
    for pattern, replacement in _DIR_ABBR.items():
        street = re.sub(pattern, replacement, street, flags=re.IGNORECASE)

    # 3. Expand street-type abbreviations
    for pattern, replacement in _SUFFIX_ABBR.items():
        street = re.sub(pattern, replacement, street, flags=re.IGNORECASE)

    # 4. Reassemble and collapse whitespace
    normalized = f"{street}, {rest}".strip(', ') if rest else street
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def fuzzy_best_match(query: str, candidates: list, key: str = 'address') -> dict | None:
    """
    Given a list of candidate dicts (each with a `key` field), returns the
    one whose address best fuzzy-matches `query` (using SequenceMatcher).
    Returns None if candidates is empty.
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    query_norm = normalize_address_for_search(query).lower()
    best = max(
        candidates,
        key=lambda c: SequenceMatcher(
            None, query_norm, normalize_address_for_search(c.get(key, '')).lower()
        ).ratio()
    )
    return best
