"""
Property Type Resolver — Multi-source detection chain.

Determines whether a property is Residential or Commercial using
multiple data sources in priority order:

    1. HCAD Bulk DB (state_class column) — instant, most authoritative
    2. RentCast API (propertyType) — good for ~80% residential
    3. RealEstateAPI (propertyType / landUse) — additional coverage
    4. HCAD Live Scraper (State Class from portal) — slow but authoritative

Returns: ("Residential" | "Commercial" | "Unknown", source_description)
"""

import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# ── HCAD State Class → Property Type Mapping ─────────────────────────────
# A = Real Residential    B = Mobile Home       C = Vacant Lot
# D = Qualified Ag Land   E = Exempt            F = Commercial Real
# G = Oil/Gas/Mineral     H = Other Non-exempt  J = Utilities
# K = Commercial Personal L = Business Personal X = Totally Exempt
RESIDENTIAL_PREFIXES = ("A", "B")
COMMERCIAL_PREFIXES  = ("F", "G", "H", "J", "K", "L")
VACANT_PREFIXES      = ("C", "D")
EXEMPT_PREFIXES      = ("E", "X")

# RentCast propertyType values
RENTCAST_RESIDENTIAL = {
    "Single Family", "Condo", "Townhouse", "Manufactured", "Multi-Family",
}
RENTCAST_COMMERCIAL = {
    "Apartment", "Land",
}

# RealEstateAPI landUse / propertyType values (case-insensitive matching)
REAPI_RESIDENTIAL_KEYWORDS = {
    "sfr", "single family", "residential", "condo", "townhouse",
    "duplex", "triplex", "quadplex",
}
REAPI_COMMERCIAL_KEYWORDS = {
    "commercial", "industrial", "retail", "office", "warehouse",
    "hotel", "motel", "mixed use", "mixed-use", "apartment",
    "store", "restaurant", "manufacturing", "flex",
}


def classify_state_class(state_class: str) -> Optional[str]:
    """Classify a property using HCAD state class code."""
    if not state_class:
        return None
    sc = state_class.strip().upper()
    first = sc[0] if sc else ""
    if first in RESIDENTIAL_PREFIXES:
        return "Residential"
    if first in COMMERCIAL_PREFIXES:
        return "Commercial"
    if first in VACANT_PREFIXES:
        return "Commercial"  # Vacant land → treated as commercial for comps
    if first in EXEMPT_PREFIXES:
        return "Commercial"  # Exempt properties → commercial treatment
    return None


async def resolve_property_type(
    account_number: str,
    address: str,
    district: str = "HCAD",
    cached_property: dict = None,
) -> Tuple[str, str]:
    """
    Multi-source property type detection.

    Args:
        account_number: The property account number.
        address: The property address (may be empty for numeric-only lookups).
        district: The expected appraisal district.
        cached_property: Optional pre-fetched DB record to avoid redundant Supabase calls.

    Returns:
        (property_type, source) where property_type is "Residential",
        "Commercial", or "Unknown", and source describes which data
        source determined the classification.
    """

    # ── Layer 1: HCAD Bulk DB (state_class column) ────────────────────
    try:
        from backend.db.supabase_client import supabase_service
        prop = cached_property  # Reuse pre-fetched record if available
        if not prop:
            prop = await supabase_service.get_property_by_account(account_number)
        if prop and prop.get("state_class"):
            sc = prop["state_class"]
            ptype = classify_state_class(sc)
            if ptype:
                logger.info(f"PropertyTypeResolver: {ptype} from DB state_class='{sc}' for {account_number}")
                return ptype, f"HCAD_DB({sc})"
    except Exception as e:
        logger.warning(f"PropertyTypeResolver: DB lookup failed: {e}")

    # ── Layer 2: RentCast API ─────────────────────────────────────────
    # Guard: skip RentCast if address is empty or purely numeric (account number)
    has_real_address = address and any(c.isalpha() for c in address)
    if has_real_address:
        try:
            from backend.agents.non_disclosure_bridge import NonDisclosureBridge
            bridge = NonDisclosureBridge()
            rc_type = await bridge.detect_property_type(address)
            if rc_type:
                if rc_type in RENTCAST_RESIDENTIAL:
                    logger.info(f"PropertyTypeResolver: Residential from RentCast='{rc_type}' for {address}")
                    return "Residential", f"RentCast({rc_type})"
                if rc_type in RENTCAST_COMMERCIAL:
                    logger.info(f"PropertyTypeResolver: Commercial from RentCast='{rc_type}' for {address}")
                    return "Commercial", f"RentCast({rc_type})"
                # Unknown RentCast type — don't decide, fall through
                logger.info(f"PropertyTypeResolver: RentCast returned '{rc_type}' — unrecognized, trying next source")
        except Exception as e:
            logger.warning(f"PropertyTypeResolver: RentCast failed: {e}")
    else:
        logger.info(f"PropertyTypeResolver: Skipping RentCast — address '{address}' is empty or numeric-only")

    # ── Layer 3: RealEstateAPI ────────────────────────────────────────
    try:
        from backend.agents.realestate_api_connector import RealEstateAPIConnector
        re_api = RealEstateAPIConnector()
        details = re_api.get_property_detail(address)
        if details:
            # Check normalized propertyType + raw landUse/propertyUse fields
            raw = details.get("_raw", {})
            fields_to_check = {
                "propertyType": details.get("property_type", ""),
                "landUse": raw.get("landUse", ""),
                "propertyUse": raw.get("propertyUse", ""),
            }
            for field_name, val in fields_to_check.items():
                val = str(val or "").lower().strip()
                if not val:
                    continue
                if any(kw in val for kw in REAPI_COMMERCIAL_KEYWORDS):
                    logger.info(f"PropertyTypeResolver: Commercial from RealEstateAPI {field_name}='{val}' for {address}")
                    return "Commercial", f"RealEstateAPI({field_name}={val})"
                if any(kw in val for kw in REAPI_RESIDENTIAL_KEYWORDS):
                    logger.info(f"PropertyTypeResolver: Residential from RealEstateAPI {field_name}='{val}' for {address}")
                    return "Residential", f"RealEstateAPI({field_name}={val})"
    except Exception as e:
        logger.warning(f"PropertyTypeResolver: RealEstateAPI failed: {e}")

    # ── Layer 4: HCAD Live Scraper (expensive — browser launch) ───────
    # Only attempt if the district is HCAD and we have an account number
    if district == "HCAD" and account_number and not any(c.isalpha() for c in account_number):
        try:
            from backend.agents.hcad_scraper import HCADScraper
            scraper = HCADScraper()
            scraped = await scraper.get_property_details(account_number, address)
            if scraped and scraped.get("property_type"):
                sc = scraped["property_type"]
                ptype = classify_state_class(sc)
                if ptype:
                    # Also save to DB for next time
                    try:
                        await supabase_service.client.table("properties").update(
                            {"state_class": sc}
                        ).eq("account_number", account_number).execute()
                    except:
                        pass
                    logger.info(f"PropertyTypeResolver: {ptype} from HCAD scraper state_class='{sc}' for {account_number}")
                    return ptype, f"HCAD_Scraper({sc})"
        except Exception as e:
            logger.warning(f"PropertyTypeResolver: HCAD scraper failed: {e}")

    # ── No source could determine the type ────────────────────────────
    logger.warning(f"PropertyTypeResolver: Could not determine type for {address} ({account_number}) — flagging as Unknown")
    return "Unknown", "NoSource"
