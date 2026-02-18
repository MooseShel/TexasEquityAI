import logging
import httpx
from typing import Optional, Dict, List
from .base_connector import AppraisalDistrictConnector

logger = logging.getLogger(__name__)

class CCADConnector(AppraisalDistrictConnector):
    """
    Connector for Collin Central Appraisal District (CCAD).
    Uses Socrata Open Data API — the gold standard approach (no scraping needed).
    """
    DISTRICT_NAME = "CCAD"
    
    # 2025 Dataset ID: vffy-snc6
    DATASET_ID = "vffy-snc6" 
    BASE_URL = "https://data.texas.gov/resource"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_property_details(self, account_number: str, address: Optional[str] = None) -> Optional[Dict]:
        logger.info(f"CCAD Lookup: {account_number}")
        
        where = ""
        if account_number:
            clean_acc = account_number.upper().strip()
            # R numbers in CCAD are usually R-XXXX-XXX-XXXX-X
            if clean_acc.startswith("R") and "-" not in clean_acc:
                where = f"geoid like '%{clean_acc}%'"
            else:
                where = f"geoid = '{clean_acc}'"
        
        if not where and address:
             addr_upper = address.upper().split(",")[0].strip()
             where = f"upper(situsconcat) like '%{addr_upper}%'"

        if not where:
             return None

        params = {
            "$where": where,
            "$limit": 1
        }
        
        try:
            resp = await self.client.get(f"{self.BASE_URL}/{self.DATASET_ID}.json", params=params)
            resp.raise_for_status()
            data = resp.json()
            
            if not data:
                # Try partial match if exact failed
                if "=" in where:
                    params["$where"] = where.replace("=", "like")
                    resp = await self.client.get(f"{self.BASE_URL}/{self.DATASET_ID}.json", params=params)
                    data = resp.json()
                
                if not data:
                    logger.warning(f"CCAD: No data found for '{account_number}'")
                    return None
            
            return self._normalize_data(data[0])

        except Exception as e:
            logger.error(f"CCAD Query Error: {e}")
            return None

    async def get_neighbors_by_street(self, street_name: str) -> List[Dict]:
        """
        Fetches neighbors by street name via Socrata API.
        Limit increased to 50 for better equity pool coverage.
        """
        logger.info(f"CCAD: Neighbor Discovery by street: {street_name}")
        street_upper = street_name.upper().strip()
        
        params = {
            "$where": f"upper(situsconcat) like '%{street_upper}%'", 
            "$limit": 50
        }
        
        try:
            resp = await self.client.get(f"{self.BASE_URL}/{self.DATASET_ID}.json", params=params)
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            for item in data:
                norm = self._normalize_data(item)
                if norm and norm.get('building_area', 0) > 0:
                    results.append(norm)
            
            logger.info(f"CCAD: Found {len(results)} valid neighbors on '{street_name}'")
            return results
        except Exception as e:
            logger.error(f"CCAD: Neighbor Error: {e}")
            return []

    async def get_neighbors(self, neighborhood_code: str) -> List[Dict]:
        """
        Fetches all properties in a neighborhood code via Socrata API.
        This is extremely fast since it's a direct API query.
        """
        if self.is_commercial_neighborhood_code(neighborhood_code):
            logger.info(f"CCAD: Skipping neighborhood search for commercial code '{neighborhood_code}'")
            return []
        
        logger.info(f"CCAD: Searching for neighborhood code: {neighborhood_code}")
        nbhd_upper = neighborhood_code.upper().strip()
        
        params = {
            "$where": f"upper(nbhdcode) = '{nbhd_upper}'",
            "$limit": 100
        }
        
        try:
            resp = await self.client.get(f"{self.BASE_URL}/{self.DATASET_ID}.json", params=params)
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            for item in data:
                norm = self._normalize_data(item)
                if norm and norm.get('building_area', 0) > 0:
                    results.append(norm)
            
            logger.info(f"CCAD: Found {len(results)} properties in neighborhood '{neighborhood_code}'")
            return results
        except Exception as e:
            logger.error(f"CCAD: Neighborhood Error: {e}")
            return []

    def _normalize_data(self, item: Dict) -> Dict:
        """Normalizes a raw Socrata API record into the standard schema."""
        return {
            "account_number": item.get("geoid", ""),
            "address": item.get("situsconcat", "Unknown"),
            "appraised_value": float(item.get("currvalappraised") or 0), 
            "market_value": float(item.get("currvalmarket") or 0),
            "building_area": float(item.get("imprvmainarea") or 0), 
            "year_built": int(item.get("imprvyearbuilt") or 0),
            "neighborhood_code": item.get("nbhdcode", "Unknown"),
            "legal_description": item.get("legaldescription", ""),
            "district": "CCAD"
        }

    def check_service_status(self) -> bool:
        return True
