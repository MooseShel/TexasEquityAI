import os
import requests
import logging
from typing import List, Optional
from backend.models.sales_comp import SalesComparable

logger = logging.getLogger(__name__)

class RealEstateAPIConnector:
    """
    Connector for RealEstateAPI.com to fetch sales comparables.
    Documentation: https://api.realestateapi.com/v2/PropertyComps
    """
    def __init__(self):
        self.api_key = os.getenv("REALESTATEAPI_KEY")
        self.base_url = "https://api.realestateapi.com/v2"

    def check_api_key(self) -> bool:
        if not self.api_key:
            logger.error("RealEstateAPI Key is missing. Please set REALESTATEAPI_KEY in .env")
            return False
        return True

    def get_sales_comparables(self, address: str, property_type: str = "Residential") -> List[SalesComparable]:
        """
        Fetch sales comparables from RealEstateAPI.
        """
        if not self.check_api_key():
            return []

        # Endpoint: POST /PropertyComps is common for rich searches, or GET. 
        # Based on typical patterns, we'll try POST if parameters are complex, 
        # but let's try the simple GET or POST approach. 
        # API docs usually suggest POST for address matching.
        
        url = f"{self.base_url}/PropertyComps"
        
        # Headers
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Payload
        # We need to structure the address. 
        # Most APIs take a single string or parts. 
        # Let's assume a simple address string payload based on standard practices for this API.
        payload = {
            "address": address,
            # "limit": 10, # Caused validation error
            # "days_old": 365, # Caused validation error
            # "radius": 1.0 # Optional, default usually 1 mile
        }

        try:
            logger.info(f"RealEstateAPI: Fetching sales comps for {address}...")
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"RealEstateAPI Error {response.status_code}: {response.text}")
                return []
            
            data = response.json()
            # Parse response. Structure is likely: 
            # { "comps": [ { "address": ..., "price": ..., "date": ... } ] } 
            # OR simple list.
            
            # Since we don't have the exact schema, we will wrap in try/except 
            # and log the keys to debug if it fails on first run.
            
            comps = data.get('comps', []) if isinstance(data, dict) else data
            
            sales_comps = []
            for comp in comps:
                # Mapping fields - adjusting based on likely JSON keys
                # address, soldPrice, soldDate, squareFootage, yearBuilt
                try:
                    c_addr = comp.get('address', {}).get('deliveryLine', comp.get('address')) # potentially nested
                    if not c_addr: continue
                    
                    price = comp.get('soldPrice') or comp.get('price') or 0
                    date = comp.get('soldDate') or comp.get('date')
                    sqft = comp.get('squareFootage') or comp.get('buildingSize') or 0
                    
                    # Calculate PPS
                    pps = price / sqft if sqft and sqft > 0 else 0
                    
                    sales_comps.append(SalesComparable(
                        address=str(c_addr),
                        sale_price=float(price),
                        sale_date=str(date) if date else None,
                        sqft=int(sqft),
                        price_per_sqft=float(pps),
                        year_built=comp.get('yearBuilt'),
                        source="RealEstateAPI",
                        dist_from_subject=comp.get('distance')
                    ))
                except Exception as e:
                    logger.warning(f"Error parsing comp: {e}")
                    continue
            
            logger.info(f"RealEstateAPI: Found {len(sales_comps)} comparables.")
            return sales_comps

        except Exception as e:
            logger.error(f"RealEstateAPI Request Failed: {e}")
            return []

    def get_property_detail(self, address: str) -> Optional[dict]:
        """
        Fetch detailed property info including mortgage history.
        Endpoint: POST /v2/PropertyDetail
        """
        if not self.check_api_key():
            return None

        url = f"{self.base_url}/PropertyDetail"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {"address": address}

        try:
            logger.info(f"RealEstateAPI: Fetching details/mortgage for {address}...")
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                logger.error(f"RealEstateAPI Detail Error {response.status_code}: {response.text}")
                return None
            return response.json()
        except Exception as e:
            logger.error(f"RealEstateAPI Detail Request Failed: {e}")
            return None
