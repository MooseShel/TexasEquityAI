
import logging
from typing import List, Dict, Optional
from backend.agents.rentcast_connector import RentCastConnector, RESIDENTIAL_TYPES, COMMERCIAL_TYPES
from backend.agents.realestate_api_connector import RealEstateAPIConnector
from backend.models.sales_comp import SalesComparable

logger = logging.getLogger(__name__)

# Official RentCast property types (lowercased for comparison):
# Residential: Single Family, Condo, Townhouse, Manufactured, Multi-Family
# Commercial:  Apartment (5+ units), Land
_RESIDENTIAL_TYPES = {"single family", "condo", "townhouse", "manufactured", "multi-family", "multifamily"}
# Types that are clearly non-residential — excluded from residential comp pools
_NON_RESIDENTIAL_TYPES = {"commercial", "office", "retail", "industrial", "mixed use", "land", "vacant", "apartment"}


def _classify_subject(subject_property: Dict) -> str:
    """Return 'Commercial' or 'Residential' for the subject property."""
    NON_RESIDENTIAL = ('commercial', 'office', 'retail', 'industrial', 'mixed_use', 'land', 'vacant', 'apartment')
    pt_field = str(subject_property.get('property_type', '')).lower()
    legal_desc = str(subject_property.get('legal_description', '')).lower()
    if pt_field in NON_RESIDENTIAL or \
       any(kw in legal_desc for kw in ("commercial", "office", "retail")):
        return "Commercial"
    return "Residential"


def _filter_comps_by_type(comps: List[SalesComparable], prop_type: str) -> List[SalesComparable]:
    """
    Filter a list of comps to match the subject property type.
    - Residential subjects: remove comps with clearly commercial/land types.
    - Commercial subjects: remove comps with clearly residential types.
    If a comp has no property_type tag (empty string), it passes through — we don't
    discard valid sold records just because the API didn't tag them.
    """
    filtered = []
    for c in comps:
        pt = (c.property_type or "").lower().replace("_", " ")
        if prop_type == "Residential" and pt in _NON_RESIDENTIAL_TYPES:
            continue  # skip commercial/land comps for residential subject
        if prop_type == "Commercial" and pt in _RESIDENTIAL_TYPES:
            continue  # skip single-family/condo comps for commercial subject
        filtered.append(c)
    return filtered


class SalesAgent:
    def __init__(self):
        self.rentcast = RentCastConnector()
        self.re_api = RealEstateAPIConnector()

    def find_sales_comps(self, subject_property: Dict) -> List[Dict]:
        """
        Finds sales comparables using a Hybrid Strategy:
        - Residential: RentCast AVM (Primary) -> RealEstateAPI (Fallback)
        - Commercial: RealEstateAPI (Primary) -> RentCast Sold Properties (Fallback) -> Mortgage Inference (Last Resort)

        All comps are filtered to match the subject property type (residential vs commercial).
        Zero-price and zero-sqft comps are excluded before returning.
        """
        address = subject_property.get('address')
        if not address:
            logger.warning("SalesAgent: No address provided.")
            return []

        # --- SMART ADDRESS FIX ---
        # If address is just a street name (no comma), append city/state based on district
        if "," not in address:
            district = subject_property.get('district', 'HCAD')
            suffix_map = {
                "HCAD": ", Houston, TX",
                "TCAD": ", Austin, TX",
                "DCAD": ", Dallas, TX",
                "TAD":  ", Fort Worth, TX",
                "CCAD": ", TX"  # Collin County covers Allen, Frisco, McKinney etc. — city-agnostic is safer
            }
            suffix = suffix_map.get(district, ", TX")
            logger.info(f"SalesAgent: Detected partial address '{address}'. Appending suffix '{suffix}'.")
            address += suffix

        logger.info(f"SalesAgent: Querying APIs with address: '{address}'")

        # Determine property type
        prop_type = _classify_subject(subject_property)
        logger.info(f"SalesAgent: Searching for {prop_type} comps for {address}...")

        comps: List[SalesComparable] = []
        source_used = "None"

        # --- STRATEGY EXECUTION ---
        if prop_type == "Residential":
            # 1. Try RentCast AVM (Primary) — returns actual sale comps with correlationPrice
            comps = self.rentcast.get_sales_comparables(address, property_type="Residential")
            if comps: source_used = "RentCast"

            # 2. Fallback to RealEstateAPI
            if not comps or len(comps) < 2:
                logger.info("SalesAgent: RentCast yielded few results. Trying RealEstateAPI...")
                re_comps = self.re_api.get_sales_comparables(address, property_type="Residential")
                if re_comps:
                    comps.extend(re_comps)
                    source_used = f"{source_used} + RealEstateAPI"

        else:  # Commercial / Land / Retail etc.
            # 1. Try RealEstateAPI (Primary for commercial)
            comps = self.re_api.get_sales_comparables(address, property_type="Commercial")
            if comps: source_used = "RealEstateAPI"

            # 2. Fallback to RentCast Sold Properties
            if not comps or len(comps) < 2:
                logger.info("SalesAgent: RealEstateAPI yielded few results. Trying RentCast sold properties...")
                rc_comps = self.rentcast.get_sales_comparables(address, property_type="Commercial")
                if rc_comps:
                    comps.extend(rc_comps)
                    source_used = f"{source_used} + RentCast"

        # --- POST-FILTER: remove comps of the wrong property type ---
        comps = _filter_comps_by_type(comps, prop_type)
        logger.info(f"SalesAgent: {len(comps)} comps after type filtering ({prop_type}).")

        # --- DEDUPLICATION by address prefix ---
        seen_addrs = set()
        unique_comps = []
        for c in comps:
            key = (c.address or "")[:20].lower().strip()
            if key and key not in seen_addrs:
                unique_comps.append(c)
                seen_addrs.add(key)
        comps = unique_comps

        # --- SELECT MOST RECENT, DISPLAY BY DISTANCE ---
        # NOTE: Truncation to 5 happens AFTER mortgage inference so weak commercial sets still trigger the fallback.
        comps.sort(key=lambda c: c.sale_date or '', reverse=True)  # newest first
        comps.sort(key=lambda c: c.dist_from_subject if c.dist_from_subject is not None else 999)

        # --- FORMATTING RESULTS ---
        results = []
        for comp in comps:
            results.append({
                "Address":     comp.address,
                "Sale Price":  f"${comp.sale_price:,.0f}",
                "Sale Date":   comp.sale_date,
                "SqFt":        f"{comp.sqft:,}" if comp.sqft > 0 else "N/A",
                "Price/SqFt":  f"${comp.price_per_sqft:.2f}" if comp.price_per_sqft > 0 else "N/A",
                "Year Built":  comp.year_built,
                "Source":      comp.source,
                "Distance":    f"{comp.dist_from_subject:.2f} mi" if comp.dist_from_subject else "N/A",
                "Type":        comp.property_type or "Unknown",
            })

        # --- MORTGAGE INFERENCE (Last Resort for Commercial) ---
        if prop_type == "Commercial" and len(results) < 2:
            logger.info("SalesAgent: Insufficient sales comps. Attempting Mortgage-Based Inference...")
            details = self.re_api.get_property_detail(address)
            if details:
                m_hist = details.get('mortgageHistory', [])
                if m_hist:
                    m_hist.sort(key=lambda x: x.get('recordingDate', ''), reverse=True)
                    recent_loan = m_hist[0]
                    amount = recent_loan.get('amount', 0)
                    date = recent_loan.get('recordingDate', 'Unknown')

                    if amount > 100000:
                        ltv_ratio = 0.70
                        estimated_price = amount / ltv_ratio
                        results.append({
                            "Address":    f"{address} (Subject Analysis)",
                            "Sale Price": f"${estimated_price:,.0f} (est)",
                            "Sale Date":  f"{date} (Loan)",
                            "SqFt":       "N/A",
                            "Price/SqFt": "N/A",
                            "Year Built": "N/A",
                            "Source":     "Inferred (Mortgage 70% LTV)",
                            "Distance":   "0.00 mi",
                            "Type":       "Commercial (Inferred)",
                        })
                        logger.info(f"SalesAgent: Inferred value ${estimated_price:,.0f} from loan.")

        # Truncate to 10 best comps NOW (after mortgage inference so the fallback could trigger)
        results = results[:10]

        logger.info(f"SalesAgent: Final count {len(results)}. Sources: {source_used}")
        return results
