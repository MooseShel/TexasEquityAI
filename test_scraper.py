import asyncio
import logging
from backend.agents.hcad_scraper import HCADScraper

logging.basicConfig(level=logging.INFO)

async def test_scraper():
    scraper = HCADScraper()
    account_number = "0660460360030"
    print(f"Testing scraper for account: {account_number}")
    
    try:
        details = await scraper.get_property_details(account_number)
        if details:
            print("Successfully scraped details:")
            print(details)
        else:
            print("Scraper returned None")
    except Exception as e:
        print(f"Scraper error: {e}")

if __name__ == "__main__":
    asyncio.run(test_scraper())
