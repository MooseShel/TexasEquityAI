"""Debug HCAD search for '8405 Hempstead' (no suffix)."""
import asyncio
from dotenv import load_dotenv
load_dotenv()

async def main():
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    from backend.agents.hcad_scraper import HCADScraper
    scraper = HCADScraper()
    
    term = "8405 Hempstead" # No "Rd", No "Hwy", No "Road"
    print(f"\n--- Testing Search Term: '{term}' ---")
    try:
        results = await scraper.get_neighbors_by_street("Debug", search_term=term)
        print(f"Found {len(results)} results for '{term}'")
        for r in results:
            print(f"  [{r['account_number']}] {r['address']}")
    except Exception as e:
        print(f"Error searching '{term}': {e}")

asyncio.run(main())
