from abc import ABC, abstractmethod
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

class AppraisalDistrictConnector(ABC):
    """
    Abstract base class for all appraisal district connectors.
    Enforces a standard interface for fetching property details and neighbors.
    """

    @abstractmethod
    async def get_property_details(self, account_number: str, address: Optional[str] = None) -> Optional[Dict]:
        """
        Fetches property details from the district's data source.
        
        Args:
            account_number: The unique account/parcel ID.
            address: Optional address to fallback or verify.
            
        Returns:
            Dict containing standardized property details (see implementation plan), or None if not found.
        """
        pass

    @abstractmethod
    async def get_neighbors_by_street(self, street_name: str) -> List[Dict]:
        """
        Searches for neighbors on the same street.
        
        Args:
            street_name: The name of the street (e.g., "LAMONTE LN").
            
        Returns:
            List of dictionaries, each representing a neighbor property.
        """
        pass

    @abstractmethod
    def check_service_status(self) -> bool:
        """
        Checks if the district's service is reachable.
        """
        pass
