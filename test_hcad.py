import asyncio
from backend.agents.hcad_scraper import HCADScraper
import logging

logging.basicConfig(level=logging.INFO)

async def test():
    scraper = HCADScraper()
    print("Testing '8100 Washington Avenue, Houston TX'")
    res1 = await scraper.get_property_details('8100 Washington Avenue, Houston TX')
    print("Result 1:", res1)
    
    print("\nTesting '8100 Washington'")
    res2 = await scraper.get_property_details('8100 Washington')
    print("Result 2:", res2)

asyncio.run(test())
