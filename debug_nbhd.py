import asyncio
import logging
import sys
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add current directory to path
sys.path.append(os.getcwd())
try:
    from backend.agents.hcad_scraper import HCADScraper
except ImportError:
    print("Could not import HCADScraper. Make sure you are in the project root.")
    sys.exit(1)

async def test_live_extraction():
    scraper = HCADScraper()
    # Using 935 Lamonte Ln (likely the user's test case)
    # Account for 935 Lamonte Ln: 0660460360012
    # Account for 843 Lamonte Ln: 0660460360030
    test_accounts = ["0660460360030", "0660460360012"]
    
    for account in test_accounts:
        print(f"\n{'='*50}")
        print(f"Testing extraction for account: {account}")
        print(f"{'='*50}")
        
        details = await scraper.get_property_details(account)
        
        if details:
            print("\n--- RESULTS ---")
            for key, value in details.items():
                print(f"{key}: {value}")
            
            nbhd = details.get('neighborhood_code')
            if nbhd and nbhd != "Unknown":
                print(f"\n✅ SUCCESS: Neighborhood Code '{nbhd}' found.")
            else:
                print("\n❌ FAILURE: Neighborhood Code missing.")
        else:
            print("\n❌ CRITICAL: Scraper returned None.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(test_live_extraction())
