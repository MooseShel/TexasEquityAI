from abc import ABC, abstractmethod
from typing import Optional, Dict, List
import logging
import re

logger = logging.getLogger(__name__)

class AppraisalDistrictConnector(ABC):
    """
    Abstract base class for all appraisal district connectors.
    Enforces a standard interface for fetching property details and neighbors.
    
    Standard output schema for get_property_details:
        account_number: str
        address: str
        appraised_value: float
        market_value: float
        building_area: float
        year_built: int | None
        neighborhood_code: str | None
        district: str  (e.g. "HCAD", "TAD", "DCAD", "TCAD", "CCAD")
    """

    # Commercial neighborhood code keywords — skip neighborhood-wide search for these
    COMMERCIAL_KEYWORDS = [
        "general", "commercial", "industrial", "service", "office",
        "retail", "warehouse", "manufacturing", "food", "hotel",
        "motel", "apartment", "multi", "mixed"
    ]

    @abstractmethod
    async def get_property_details(self, account_number: str, address: Optional[str] = None) -> Optional[Dict]:
        """
        Fetches property details from the district's data source.
        
        Args:
            account_number: The unique account/parcel ID.
            address: Optional address to fallback or verify.
            
        Returns:
            Dict containing standardized property details, or None if not found.
        """
        pass

    @abstractmethod
    async def get_neighbors_by_street(self, street_name: str) -> List[Dict]:
        """
        Searches for neighbors on the same street.
        
        Args:
            street_name: The name of the street (e.g., "LAMONTE LN").
            
        Returns:
            List of dicts, each representing a neighbor property.
        """
        pass

    async def get_neighbors(self, neighborhood_code: str) -> List[Dict]:
        """
        Searches for all properties in a neighborhood code.
        Default implementation returns empty list — override in connectors that support it.
        
        Args:
            neighborhood_code: The neighborhood/market area code.
            
        Returns:
            List of dicts, each representing a neighbor property.
        """
        return []

    @abstractmethod
    def check_service_status(self) -> bool:
        """
        Checks if the district's service is reachable.
        """
        pass

    # ─── Shared Utility Methods ───────────────────────────────────────────────

    def _parse_currency(self, text: str) -> float:
        """Parse a currency string like '$1,234,567' or '1234567' into a float."""
        if not text:
            return 0.0
        clean = re.sub(r'[$,\s]', '', str(text))
        if not clean or "pending" in clean.lower() or "n/a" in clean.lower():
            return 0.0
        try:
            return float(clean)
        except (ValueError, TypeError):
            return 0.0

    def _parse_number(self, text: str) -> float:
        """Parse a numeric string like '1,234' into a float."""
        if not text:
            return 0.0
        clean = re.sub(r'[,\s]', '', str(text))
        try:
            return float(clean)
        except (ValueError, TypeError):
            return 0.0

    def is_commercial_neighborhood_code(self, neighborhood_code: str) -> bool:
        """
        Returns True if the neighborhood code appears to be commercial/non-residential.
        Commercial codes should not be used for residential equity analysis.
        """
        if not neighborhood_code or neighborhood_code in ("Unknown", ""):
            return False
        code_lower = neighborhood_code.lower()
        return any(kw in code_lower for kw in self.COMMERCIAL_KEYWORDS)
