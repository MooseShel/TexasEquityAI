import os
import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class NonDisclosureBridge:
    def __init__(self):
        self.api_key = os.getenv("BATCHDATA_API_KEY")
        self.use_mock = not self.api_key

    async def get_last_sale_price(self, address: str) -> Optional[float]:
        if self.use_mock:
            logger.info(f"Using mock data for address: {address}")
            # Mock data based on typical Harris County values
            return 350000.0 if "Harris" in address or True else None
        
        # BatchData Property API Implementation (Simplified)
        try:
            url = f"https://api.batchdata.com/api/v1/property/search?address={address}"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [{}])[0].get("last_sale_price")
            return None
        except Exception as e:
            logger.error(f"Error fetching from BatchData: {e}")
            return None

    def calculate_fallback_value(self, neighborhood_sales: list) -> float:
        """
        Calculate 'Estimated Market Value' by applying a neighborhood-level 
        'Sales-to-Appraisal Ratio' derived from the nearest 10 known sales.
        """
        if not neighborhood_sales or len(neighborhood_sales) < 1:
            return 0.0
        
        ratios = []
        for sale in neighborhood_sales[:10]:
            if sale.get('appraised_value') and sale.get('sale_price'):
                ratios.append(sale['sale_price'] / sale['appraised_value'])
        
        if not ratios:
            return 0.0
            
        median_ratio = sorted(ratios)[len(ratios)//2]
        return median_ratio

    async def get_estimated_market_value(self, appraised_value: float, address: str) -> float:
        # For MVP, we'll use a dummy set of neighborhood sales
        mock_neighborhood_sales = [
            {'appraised_value': 300000, 'sale_price': 315000}, # 1.05
            {'appraised_value': 310000, 'sale_price': 325500}, # 1.05
            {'appraised_value': 290000, 'sale_price': 304500}, # 1.05
            {'appraised_value': 320000, 'sale_price': 336000}, # 1.05
            {'appraised_value': 305000, 'sale_price': 320250}, # 1.05
        ]
        
        ratio = self.calculate_fallback_value(mock_neighborhood_sales)
        return appraised_value * ratio
