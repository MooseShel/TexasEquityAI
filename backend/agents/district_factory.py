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
    def detect_district_from_account(account_number: str) -> Optional[str]:
        """
        Analyzes account number format to guess the district.
        """
        if not account_number: return None
        
        clean_acc = account_number.replace("-", "").strip()
        
        # DCAD: 17 characters (often has dashes, but we cleaned them)
        # Actually DCAD is usually just long.
        if len(clean_acc) == 17:
             return "DCAD"

        # HCAD: 13 digits
        if len(clean_acc) == 13 and clean_acc.isdigit():
             return "HCAD"
            
        # CCAD: Often starts with R
        if account_number.upper().startswith("R"):
             return "CCAD"
        
        # TCAD: Usually 6 digits (up to 7)
        if len(clean_acc) <= 7 and clean_acc.isdigit():
            return "TCAD"
            
        # TAD: 8 digits
        if len(clean_acc) == 8 and clean_acc.isdigit():
            return "TAD"
             
        return None

    @staticmethod
    def get_connector(district_code: Optional[str] = None, account_number: Optional[str] = None) -> AppraisalDistrictConnector:
        """
        Returns a connector instance.
        """
        # 1. Try to detect from account number first (Verification Step)
        # If we have an account number, we might want to ensure the district matches
        # But for now, we follow the logic: Use explicit code if valid, else detect.
        
        target_district = district_code
        
        if not target_district and account_number:
            target_district = DistrictConnectorFactory.detect_district_from_account(account_number)
            
        # Default to HCAD if still unknown
        if not target_district:
            target_district = "HCAD"
            
        code = target_district.upper()
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
            
        return HCADScraper()
