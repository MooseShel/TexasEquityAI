import asyncio
import logging
from backend.agents.ccad_connector import CCADConnector

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ccad_integration():
    connector = CCADConnector()
    
    # Test Property Detail Retrieval
    # Using the geoid found in test_ccad_api.py: R-4753-00M-0010-1 (529 CAMROSE LN)
    test_account = "R-4753-00M-0010-1"
    
    print(f"\n--- Testing get_property_details for {test_account} ---")
    details = await connector.get_property_details(test_account)
    if details:
        print("Successfully retrieved details:")
        for k, v in details.items():
            print(f"  {k}: {v}")
    else:
        print("Failed to retrieve details.")

    # Test Neighbor Discovery by Street
    test_street = "CAMROSE"
    print(f"\n--- Testing get_neighbors_by_street for '{test_street}' ---")
    neighbors = await connector.get_neighbors_by_street(test_street)
    if neighbors:
        print(f"Successfully found {len(neighbors)} neighbors:")
        for n in neighbors[:5]: # Show first 5
            print(f"  Account: {n['account_number']}, Address: {n['address']}, Value: ${n['market_value']}")
    else:
        print("Failed to find neighbors.")

    await connector.client.aclose()

if __name__ == "__main__":
    asyncio.run(test_ccad_integration())
