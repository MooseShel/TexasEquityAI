import os
import requests
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class RentCastAgent:
    def __init__(self):
        self.api_key = os.getenv("RENTCAST_API_KEY")
        self.base_url = "https://api.rentcast.io/v1/properties"

    async def get_sale_data(self, address: str) -> Optional[Dict]:
        if not self.api_key: 
            logger.warning("RentCast API Key missing.")
            return None
        try:
            headers = {"X-Api-Key": self.api_key, "accept": "application/json"}
            params = {"address": address}
            logger.info(f"Querying RentCast for: {address}")
            response = requests.get(self.base_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data and isinstance(data, list) and len(data) > 0:
                    prop = data[0]
                    sale_price = prop.get("lastSalePrice")
                    logger.info(f"RentCast found sale price: {sale_price}")
                    return {
                        "sale_price": sale_price,
                        "sale_date": prop.get("lastSaleDate"),
                        "source": "RentCast"
                    }
                else:
                    logger.info("RentCast returned no data for this address.")
            else:
                logger.error(f"RentCast API Error: {response.status_code} - {response.text}")
            return None
        except Exception as e:
            logger.error(f"RentCast Agent Exception: {e}")
            return None

    async def resolve_address(self, address: str) -> Optional[Dict]:
        """
        Resolves a street address to an HCAD Account Number (assessorID) and property details.
        """
        if not self.api_key: return None
        try:
            headers = {"X-Api-Key": self.api_key, "accept": "application/json"}
            params = {"address": address}
            logger.info(f"Resolving Address via RentCast: {address}")
            response = requests.get(self.base_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data and isinstance(data, list) and len(data) > 0:
                    prop = data[0]
                    # Map RentCast fields to our schema
                    details = {
                        "account_number": prop.get("assessorID"),
                        "address": prop.get("formattedAddress"),
                        "appraised_value": 0, # to be filled later or from taxAssessments if needed
                        "building_area": prop.get("squareFootage"),
                        "year_built": prop.get("yearBuilt"),
                        "legal_description": prop.get("legalDescription"),
                        "rentcast_data": prop # Keep full data for fallback
                    }
                    
                    # Try to get latest appraised value from taxAssessments
                    tax_assessments = prop.get("taxAssessments", {})
                    if tax_assessments:
                        # Get max year
                        latest_year = max(tax_assessments.keys(), key=lambda x: int(x))
                        details['appraised_value'] = tax_assessments[latest_year].get('value', 0)
                        
                    return details
            return None
        except Exception as e:
            logger.error(f"RentCast Resolution Failed: {e}")
            return None

class NonDisclosureBridge:
    def __init__(self):
        self.rentcast = RentCastAgent()

    async def get_last_sale_price(self, address: str) -> Optional[Dict]:
        # Try RentCast
        data = await self.rentcast.get_sale_data(address)
        if data and data.get("sale_price"):
            return data
            
        return None

    async def resolve_address(self, address: str) -> Optional[Dict]:
        return await self.rentcast.resolve_address(address)

    def calculate_fallback_value(self, neighborhood_sales: list) -> float:
        if not neighborhood_sales: return 1.0
        ratios = [s['sale_price'] / s['appraised_value'] for s in neighborhood_sales if s['appraised_value'] > 0]
        if not ratios: return 1.0
        return sorted(ratios)[len(ratios)//2]

    async def get_estimated_market_value(self, appraised_value: float, address: str) -> float:
        # Without real market data, we rely on the appraised value as the best estimate
        # or potentially a conservative multiplier if we had regional trend data.
        # For now, we avoid making up numbers.
        return appraised_value
