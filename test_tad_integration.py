import asyncio
import logging
from backend.agents.tad_connector import TADConnector

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_tad():
    connector = TADConnector()
    
    print("--- Testing get_property_details ---")
    # Commercial property from previous test
    # account = "04657837" 
    # Let's try to find an account number from the earlier search "100 Weatherford"
    # The result was 04657837.
    account = "04657837"
    
    try:
        details = await connector.get_property_details(account_number=account)
        print("Details found:")
        for k, v in details.items():
            print(f"  {k}: {v}")
            
        if details.get("neighborhood_code"):
            print("\n--- Testing get_neighbors ---")
            nbhd = details["neighborhood_code"]
            print(f"Fetching neighbors for code: {nbhd}")
            neighbors = await connector.get_neighbors(nbhd)
            print(f"Found {len(neighbors)} neighbors.")
            if neighbors:
                print("First 3 neighbors:")
                for n in neighbors[:3]:
                    print(f"  {n}")
        else:
            print("\nSkipping neighbors test (no neighborhood code)")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tad())
