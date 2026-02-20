import asyncio
from backend.agents.hcad_scraper import HCADScraper
import logging

logging.basicConfig(level=logging.INFO)

async def test_golden():
    s = HCADScraper()
    print("Testing HCAD Scraper Golden Data for 0660460360030...")
    data = await s.get_property_details("0660460360030")
    print(f"Result: {data}")
    if data and data['address'] == "843 Lamonte Ln, Houston, TX 77018":
        print("VERIFICATION SUCCESS: Golden Data active.")
    else:
        print("VERIFICATION FAILED: Scraper did not return golden data.")

if __name__ == "__main__":
    asyncio.run(test_golden())
