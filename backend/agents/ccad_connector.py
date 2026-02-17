import logging
import httpx
from typing import Optional, Dict, List
from .base_connector import AppraisalDistrictConnector

logger = logging.getLogger(__name__)

class CCADConnector(AppraisalDistrictConnector):
    """
    Connector for Collin Central Appraisal District (CCAD).
    Uses Socrata API (Open Data).
    """
    
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
            # If it's a R number without dashes, Socrata might need dashes
            # Example: R281500C01001 -> R-2815-00C-0100-1 ???
            # Let's try to match it as is first, then with dashes if it looks like a CCAD pattern.
            # R numbers in CCAD are usually R-XXXX-XXX-XXXX-X
            if clean_acc.startswith("R") and "-" not in clean_acc:
                # Basic guess: R-2815-00C-0100-1 (dashes at 2, 7, 11, 16)
                # But let's use LIKE if it's tricky.
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
                    return None
            
            return self._normalize_data(data[0])

        except Exception as e:
            logger.error(f"CCAD Query Error: {e}")
            return None

    async def get_neighbors_by_street(self, street_name: str) -> List[Dict]:
        logger.info(f"CCAD Neighbor Discovery: {street_name}")
        street_upper = street_name.upper().strip()
        
        params = {
            "$where": f"upper(situsconcat) like '%{street_upper}%'", 
            "$limit": 20
        }
        
        try:
            resp = await self.client.get(f"{self.BASE_URL}/{self.DATASET_ID}.json", params=params)
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            for item in data:
                norm = self._normalize_data(item)
                if norm:
                    results.append(norm)
            return results
        except Exception as e:
            logger.error(f"CCAD Neighbor Error: {e}")
            return []

    def _normalize_data(self, item: Dict) -> Dict:
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
