import httpx
import asyncio
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# Open-data permit endpoints keyed by appraisal district
# Only HCAD (Houston) has a well-known CKAN permit API; other districts
# return empty rather than hitting the wrong city's endpoint.
_PERMIT_ENDPOINTS: Dict[str, Optional[str]] = {
    "HCAD": "https://data.houstontx.gov/api/3/action/datastore_search",
    "DCAD": None,  # Dallas open data exists but no direct building permit resource
    "TAD":  None,
    "CCAD": None,
    "TCAD": None,
}
_HCAD_RESOURCE_ID = "8729584b-013b-410a-85d8-4f8a42e74e64"


class PermitAgent:
    """
    Queries building permit records for a property.
    Currently has full data for HCAD (Houston), graceful no-op for other districts.
    Uses async httpx — does NOT block the event loop.
    """

    async def get_property_permits(self, address: str, district: str = "HCAD") -> List[Dict]:
        """
        Searches for building permits associated with a specific address.
        Returns empty list (rather than hitting a wrong city's API) for non-HCAD districts.
        """
        endpoint = _PERMIT_ENDPOINTS.get(district, None)
        if not endpoint:
            logger.info(f"PermitAgent: No permit data source for district '{district}'. Skipping.")
            return []

        search_addr = address.split(",")[0].strip()

        params = {
            "resource_id": _HCAD_RESOURCE_ID,
            "q":           search_addr,
            "limit":       10
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(endpoint, params=params)

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
            val  = p.get('declared_valuation', 0)

            if any(k in desc for k in renovation_keywords) or (val and float(val) > 10000):
                major_permits.append({
                    "date":        p.get('permit_issue_date'),
                    "description": p.get('description'),
                    "value":       val
                })

        return {
            "status":        f"Found {len(major_permits)} major permits" if major_permits else "Minor permits only",
            "has_renovations": len(major_permits) > 0,
            "major_permits": major_permits
        }

    async def summarize_comp_renovations(self, comparables: List[Dict],
                                         district: str = "HCAD") -> List[Dict]:
        """
        Checks permits for a list of comparable properties in parallel using asyncio.gather.
        """
        if not comparables:
            return []

        async def _check_one(comp: Dict) -> Optional[Dict]:
            addr = comp.get('address')
            if not addr:
                return None
            permits  = await self.get_property_permits(addr, district=district)
            analysis = self.analyze_permits(permits)
            if analysis['has_renovations']:
                return {
                    "address":          addr,
                    "renovations":      analysis['major_permits'],
                    "adjustment_logic": "Comparable has superior condition due to documented major permits."
                }
            return None

        results_raw = await asyncio.gather(*[_check_one(c) for c in comparables])
        return [r for r in results_raw if r is not None]
