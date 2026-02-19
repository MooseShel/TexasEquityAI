import os
import requests
import logging
from typing import Optional, List, Dict
from backend.models.sales_comp import SalesComparable

logger = logging.getLogger(__name__)

class RentCastConnector:
    def __init__(self):
        self.api_key = os.getenv("RENTCAST_API_KEY")
        self.base_url_comps = "https://api.rentcast.io/v1/avm/value"
        self.base_url_props = "https://api.rentcast.io/v1/properties"

    def check_api_key(self) -> bool:
        if not self.api_key:
            logger.error("RentCast API Key is missing. Please set RENTCAST_API_KEY in .env")
            return False
        return True

    def get_sales_comparables(self, address: str, property_type: str = "Residential") -> List[SalesComparable]:
        """
        Fetches sales comparables from RentCast.
        """
        if not self.check_api_key():
            return []

        try:
            headers = {"X-Api-Key": self.api_key, "accept": "application/json"}
            params = {
                "address": address,
                "propertyType": property_type if property_type != "Commercial" else None, # RentCast infers or we can omit for broad search
                "radius": 1.0, # 1 mile radius
                "compType": "sale",
                "daysOld": 365 # 1 year lookback
            }
            
            # For Commercial, we might need to rely on the general properties endpoint if AVM doesn't return good comps
            # But let's try AVM endpoint first as it's designed for comps
            logger.info(f"RentCast: Fetching sales comps for {address}...")
            response = requests.get(self.base_url_comps, headers=headers, params=params)
            
            comps_list = []
            
            if response.status_code == 200:
                data = response.json()
                if data and "comparables" in data:
                    raw_comps = data["comparables"]
                    logger.info(f"RentCast: Found {len(raw_comps)} comparables.")
                    
                    for comp in raw_comps:
                        try:
                            price = comp.get("price")
                            sqft = comp.get("squareFootage")
                            
                            if price and sqft and sqft > 0:
                                comps_list.append(SalesComparable(
                                    address=comp.get("formattedAddress") or comp.get("addressLine1"),
                                    sale_price=float(price),
                                    sale_date=comp.get("dateTaken") or comp.get("createdDate"), # Adjust based on actual API field
                                    sqft=int(sqft),
                                    price_per_sqft=round(float(price) / float(sqft), 2),
                                    year_built=comp.get("yearBuilt"),
                                    source="RentCast",
                                    dist_from_subject=comp.get("distance"),
                                    similarity_score=None # To be calculated if needed
                                ))
                        except Exception as e:
                            logger.warning(f"Skipping malformed comp: {e}")
                            continue
            else:
                logger.warning(f"RentCast API Error: {response.status_code} - {response.text}")
                
            return comps_list

        except Exception as e:
            logger.error(f"RentCast Connector Exception: {e}")
            return []
