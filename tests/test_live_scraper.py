import asyncio
import logging
import sys
import os

# Set up logging
logging.basicConfig(level=logging.INFO)

# Add parent directory to path to import backend
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), '..')))
from backend.agents.hcad_scraper import HCADScraper

async def test_live_extraction():
    scraper = HCADScraper()
    account = "0660460360030"
    address = "843 Lamonte Ln, Houston, TX 77018"
    
    print(f"Testing live extraction for account: {account}...")
    details = await scraper.get_property_details(account, address)
    
    if details:
        print("\n--- EXTRACTION SUCCESS ---")
        for key, value in details.items():
            print(f"{key}: {value}")
        
        if details.get('neighborhood_code') and details['neighborhood_code'] != "Unknown":
            print("\n✅ Neighborhood Code successfully extracted!")
        else:
            print("\n❌ Neighborhood Code missing or unknown.")
    else:
        print("\n❌ Extraction failed completely.")

if __name__ == "__main__":
    asyncio.run(test_live_extraction())
