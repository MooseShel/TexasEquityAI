from typing import Optional
from .base_connector import AppraisalDistrictConnector
from .hcad_scraper import HCADScraper
from .tad_connector import TADConnector
from .ccad_connector import CCADConnector
from .tcad_connector import TCADConnector
from .dcad_connector import DCADConnector

class DistrictConnectorFactory:
    """
    Factory to instantiate the correct AppraisalDistrictConnector
    based on account number pattern or explicit district code.
    """
    
    @staticmethod
    def get_connector(district_code: Optional[str] = None, account_number: Optional[str] = None) -> AppraisalDistrictConnector:
        """
        Returns a connector instance.
        """
        # Explicit override
        if district_code:
            code = district_code.upper()
            if code == "TAD":
                return TADConnector()
            elif code == "CCAD":
                return CCADConnector()
            elif code == "TCAD":
                return TCADConnector()
            elif code == "DCAD":
                return DCADConnector()
            elif code == "HCAD":
                return HCADScraper()
        
        # Auto-detection
        if account_number:
            clean_acc = account_number.replace("-", "").strip()
            
            # DCAD: 17 characters
            if len(clean_acc) == 17:
                return DCADConnector()

            # HCAD: 13 digits
            if len(clean_acc) == 13 and clean_acc.isdigit():
                return HCADScraper()
                
            # CCAD: Often starts with R
            if account_number.upper().startswith("R"):
                return CCADConnector()
            
            # TAD/TCAD detection can be tricky as both use numeric IDs.
            # TCAD IDs are usually 6-7 digits.
            # This is why passing district_code is preferred.
            
            # Default fallback (Legacy)
            return HCADScraper()
            
        return HCADScraper()
