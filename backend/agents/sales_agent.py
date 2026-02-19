
import logging
from typing import List, Dict, Optional
from backend.agents.rentcast_connector import RentCastConnector
from backend.models.sales_comp import SalesComparable

logger = logging.getLogger(__name__)

class SalesAgent:
    def __init__(self):
        self.rentcast = RentCastConnector()

    def find_sales_comps(self, subject_property: Dict) -> List[Dict]:
        """
        Finds sales comparables for the subject property.
        Returns a list of dictionaries ready for the report table.
        """
        address = subject_property.get('address')
        if not address:
            logger.warning("SalesAgent: No address provided for subject property.")
            return []

        # Determine Property Type (basic logic, expanding later for Commercial)
        # HCAD land use codes can help, but for now default to Residential unless 'Commercial' in description
        # improved logic: check state code or land use from subject property details if available
        prop_type = "Residential" 
        if "commercial" in str(subject_property.get('legal_description', '')).lower():
            prop_type = "Commercial"

        logger.info(f"SalesAgent: Searching for {prop_type} sales comps for {address}...")
        
        # specific logic for RentCast
        comps = self.rentcast.get_sales_comparables(address, property_type=prop_type)
        
        # Post-Processing / Filtering
        # 1. Sort by Date (Most recent first)
        # 2. Sort by Similarity (if score exists) -> currently RentCast doesn't give a score, so we use date/dist
        
        # Convert to dictionary for report
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
             
        # Create a fallback if no comps found and it's commercial?
        # For now, just return empty list. UI handles empty table.
        
        return results
