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
        if not self.api_key: return None
        try:
            headers = {"X-Api-Key": self.api_key}
            params = {"address": address}
            response = requests.get(self.base_url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                if data:
                    prop = data[0]
                    return {
                        "sale_price": prop.get("lastSalePrice"),
                        "sale_date": prop.get("lastSaleDate"),
                        "source": "RentCast"
                    }
            return None
        except Exception as e:
            logger.error(f"RentCast API Error: {e}")
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

    def calculate_fallback_value(self, neighborhood_sales: list) -> float:
        if not neighborhood_sales: return 1.0
        ratios = [s['sale_price'] / s['appraised_value'] for s in neighborhood_sales if s['appraised_value'] > 0]
        if not ratios: return 1.0
        return sorted(ratios)[len(ratios)//2]

    async def get_estimated_market_value(self, appraised_value: float, address: str) -> float:
        # Mock neighborhood for MVP fallback
        mock_neighborhood_sales = [
            {'appraised_value': 300000, 'sale_price': 315000},
            {'appraised_value': 310000, 'sale_price': 325500},
            {'appraised_value': 290000, 'sale_price': 304500},
        ]
        ratio = self.calculate_fallback_value(mock_neighborhood_sales)
        return appraised_value * ratio
