import requests
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class FEMAAgent:
    """
    Agent responsible for querying FEMA National Flood Hazard Layer (NFHL) 
    to determine if a property is in a high-risk flood zone.
    """
    def __init__(self):
        # FEMA NFHL ArcGIS REST Identify endpoint
        self.url = "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/identify"

    async def get_flood_zone(self, lat: float, lng: float) -> Optional[Dict]:
        """
        Determines the flood zone for a given coordinate.
        Returns a dict with zone info or None if lookup fails.
        """
        params = {
            "geometry": f"{lng},{lat}", # ESRI uses Long,Lat
            "geometryType": "esriGeometryPoint",
            "sr": "4326", # WGS84
            "layers": "all",
            "tolerance": "3",
            "mapExtent": f"{lng-0.01},{lat-0.01},{lng+0.01},{lat+0.01}",
            "imageDisplay": "800,600,96",
            "returnGeometry": "false",
            "f": "json"
        }
        
        try:
            # We use requests here; for high performance, we could switch to httpx/async
            response = requests.get(self.url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                # Extract Flood Hazard Zone
                zone_info = None
                for res in results:
                    if res.get('layerName') == 'Flood Hazard Zones':
                        attrs = res.get('attributes', {})
                        zone_info = {
                            "zone": attrs.get('FLD_ZONE'),
                            "subtype": attrs.get('ZONE_SUBTY'),
                            "is_high_risk": attrs.get('FLD_ZONE', '').startswith(('A', 'V')),
                            "source": "FEMA NFHL"
                        }
                        break
                
                if zone_info:
                    logger.info(f"FEMA Flood Zone found: {zone_info['zone']}")
                else:
                    logger.info("FEMA: No flood zone hazard detected at this location.")
                
                return zone_info
            else:
                logger.error(f"FEMA API Error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"FEMA Agent Exception: {e}")
            return None

    def get_deduction_argument(self, zone_info: Dict) -> Optional[Dict]:
        """
        Generates a legal/valuation argument based on the flood zone.
        """
        if not zone_info or not zone_info.get('is_high_risk'):
            return None
        
        zone = zone_info.get('zone', 'Unknown')
        
        return {
            "factor": "External Obsolescence (Flood Risk)",
            "argument": f"Property is located within FEMA Flood Zone {zone}, incurring significantly higher insurance premiums and reduced marketability compared to Zone X counterparts.",
            "impact": "High",
            "suggested_adjustment": -0.05 # 5% downward adjustment is a common starting point for flood risk
        }
