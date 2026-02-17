import asyncio
from backend.agents.hcad_scraper import HCADScraper
import logging

logging.basicConfig(level=logging.INFO)

async def test_scraper():
    scraper = HCADScraper()
    account = "0660460450034"
    print(f"Testing Scraper with account: {account}")
    
    details = await scraper.get_property_details(account)
    print(f"RESULT: {details}")

if __name__ == "__main__":
    asyncio.run(test_scraper())
