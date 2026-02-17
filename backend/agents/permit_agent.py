import requests
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class PermitAgent:
    """
    Agent responsible for querying City of Houston Building Permit records
    via the CKAN Open Data API.
    """
    def __init__(self):
        self.url = "https://data.houstontx.gov/api/3/action/datastore_search"
        # Approved Building Permits Resource ID
        self.resource_id = "8729584b-013b-410a-85d8-4f8a42e74e64"

    async def get_property_permits(self, address: str) -> List[Dict]:
        """
        Searches for building permits associated with a specific address.
        """
        # Clean address for searching (take first part before comma)
        search_addr = address.split(",")[0].strip()
        
        params = {
            "resource_id": self.resource_id,
            "q": search_addr,
            "limit": 10
        }
        
        try:
            response = requests.get(self.url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    records = data['result']['records']
                    logger.info(f"Permits found for {search_addr}: {len(records)}")
                    return records
            return []
        except Exception as e:
            logger.error(f"Permit Agent Exception: {e}")
            return []

    def analyze_permits(self, permits: List[Dict]) -> Dict:
        """
        Analyzes permit history to determine renovation status.
        """
        if not permits:
            return {"status": "No recent permits", "has_renovations": False}
        
        renovation_keywords = ["REMODEL", "RENOVATION", "ADDITION", "ALTERATION", "REHAB"]
        major_permits = []
        
        for p in permits:
            desc = str(p.get('description', '')).upper()
            val = p.get('declared_valuation', 0)
            
            # If valuation is high or description matches keywords
            if any(k in desc for k in renovation_keywords) or (val and float(val) > 10000):
                major_permits.append({
                    "date": p.get('permit_issue_date'),
                    "description": p.get('description'),
                    "value": val
                })
        
        return {
            "status": f"Found {len(major_permits)} major permits" if major_permits else "Minor permits only",
            "has_renovations": len(major_permits) > 0,
            "major_permits": major_permits
        }

    async def summarize_comp_renovations(self, comparables: List[Dict]) -> List[Dict]:
        """
        Checks permits for a list of comparable properties and flags those with recent renovations.
        """
        results = []
        for comp in comparables:
            addr = comp.get('address')
            if not addr: continue
            
            permits = await self.get_property_permits(addr)
            analysis = self.analyze_permits(permits)
            
            if analysis['has_renovations']:
                results.append({
                    "address": addr,
                    "renovations": analysis['major_permits'],
                    "adjustment_logic": "Comparable has superior condition due to documented major permits."
                })
        return results
