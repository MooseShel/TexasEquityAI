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
    
    DEPRECATION WARNING: Live web scrapers (like HCADScraper) are now 
    strictly reserved for surgical, single-property fallback operations. 
    Primary data ingestion is handled by the automated weekly 
    hcad_etl_pipeline.py (pushing normalized extract dumps directly to Supabase).
    Always verify cache availability in the Supabase 'properties' table first.
    """
    
    @staticmethod
    def detect_district_from_account(account_number: str) -> Optional[str]:
        """
        Analyzes account number format to guess the district.
        
        Known formats:
          HCAD:  exactly 13 digits           e.g. 0660460360030
          DCAD:  exactly 17 chars (no dashes) e.g. 00000776533000000
          CCAD:  starts with 'R'             e.g. R-2815-00C-0100-1
          TAD:   exactly 8 digits            e.g. 04657837
          TCAD:  6-7 digits (AMBIGUOUS with CCAD numeric IDs — do NOT auto-detect)
        """
        if not account_number: return None
        
        clean_acc = account_number.replace("-", "").strip()
        
        # DCAD: exactly 17 characters (long numeric string)
        if len(clean_acc) == 17:
            return "DCAD"

        # HCAD: exactly 13 digits
        if len(clean_acc) == 13 and clean_acc.isdigit():
            return "HCAD"
            
        # CCAD: starts with R (R-number format)
        if account_number.upper().strip().startswith("R"):
            return "CCAD"
        
        # TAD: exactly 8 digits
        if len(clean_acc) == 8 and clean_acc.isdigit():
            return "TAD"
        
        # NOTE: TCAD (6-7 digits) is intentionally NOT auto-detected here because
        # CCAD also uses plain numeric IDs of similar length (e.g. 2787425).
        # The user must select TCAD manually from the dropdown.
            
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
