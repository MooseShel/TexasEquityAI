
import logging
from typing import List, Dict, Optional
from backend.agents.rentcast_connector import RentCastConnector
from backend.agents.realestate_api_connector import RealEstateAPIConnector
from backend.models.sales_comp import SalesComparable

logger = logging.getLogger(__name__)

class SalesAgent:
    def __init__(self):
        self.rentcast = RentCastConnector()
        self.re_api = RealEstateAPIConnector()

    def find_sales_comps(self, subject_property: Dict) -> List[Dict]:
        """
        Finds sales comparables using a Hybrid Strategy:
        - Residential: RentCast (Primary) -> RealEstateAPI (Fallback)
        - Commercial: RealEstateAPI (Primary) -> RentCast (Fallback) -> Mortgage Inference (Last Resort)
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
                "CCAD": ", Plano, TX"
            }
            suffix = suffix_map.get(district, ", Houston, TX")
            logger.info(f"SalesAgent: Detected partial address '{address}'. Appending suffix '{suffix}'.")
            address += suffix
        
        logger.info(f"SalesAgent: Querying APIs with address: '{address}'")

        # Determine Property Type
        prop_type = "Residential"
        legal_desc = str(subject_property.get('legal_description', '')).lower()
        if "commercial" in legal_desc or "office" in legal_desc or "retail" in legal_desc:
            prop_type = "Commercial"

        logger.info(f"SalesAgent: Searching for {prop_type} comps for {address}...")
        
        comps = []
        source_used = "None"
        
        # --- STRATEGY EXECUTION ---
        if prop_type == "Residential":
            # 1. Try RentCast (Primary)
            comps = self.rentcast.get_sales_comparables(address, property_type="Residential")
            if comps: source_used = "RentCast (Primary)"
            
            # 2. Fallback to RealEstateAPI
            if not comps or len(comps) < 2:
                logger.info("SalesAgent: RentCast yielded few results. Trying RealEstateAPI...")
                re_comps = self.re_api.get_sales_comparables(address, property_type="Residential")
                if re_comps:
                    comps.extend(re_comps)
                    source_used = f"{source_used} + RealEstateAPI"

        else: # Commercial
            # 1. Try RealEstateAPI (Primary)
            comps = self.re_api.get_sales_comparables(address, property_type="Commercial")
            if comps: source_used = "RealEstateAPI (Primary)"
            
            # 2. Fallback to RentCast
            if not comps or len(comps) < 2:
                logger.info("SalesAgent: RealEstateAPI yielded few results. Trying RentCast...")
                rc_comps = self.rentcast.get_sales_comparables(address, property_type="Commercial")
                if rc_comps:
                    comps.extend(rc_comps)
                    source_used = f"{source_used} + RentCast"

        # --- DEDUPLICATION ---
        # Simple specific dedupe by address (first 10 chars) to avoid duplicates from both sources
        seen_addrs = set()
        unique_comps = []
        for c in comps:
            key = c.address[:15].lower()
            if key not in seen_addrs:
                unique_comps.append(c)
                seen_addrs.add(key)
        comps = unique_comps

        # --- FORMATTING RESULTS ---
        results = []
        for comp in comps:
             results.append({
                 "Address": comp.address,
                 "Sale Price": f"${comp.sale_price:,.0f}",
                 "Sale Date": comp.sale_date,
                 "SqFt": f"{comp.sqft:,}",
                 "Price/SqFt": f"${comp.price_per_sqft:.2f}",
                 "Year Built": comp.year_built,
                 "Source": comp.source,
                 "Distance": f"{comp.dist_from_subject:.2f} mi" if comp.dist_from_subject else "N/A"
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
                            "Address": f"{address} (Subject Analysis)",
                            "Sale Price": f"${estimated_price:,.0f} (est)",
                            "Sale Date": f"{date} (Loan)",
                            "SqFt": "N/A",  
                            "Price/SqFt": "N/A",
                            "Year Built": "N/A",
                            "Source": "Inferred (Mortgage 70% LTV)",
                            "Distance": "0.00 mi"
                        })
                        logger.info(f"SalesAgent: Inferred value ${estimated_price:,.0f} from loan.")

        logger.info(f"SalesAgent: Final count {len(results)}. Sources: {source_used}")
        return results
