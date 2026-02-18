import asyncio
import json
from agents.tcad_connector import TCADConnector

async def test_tcad():
    connector = TCADConnector()
    
    print("Testing TCAD Property Details for 177373...")
    details = await connector.get_property_details("177373")
    print(f"Details: {json.dumps(details, indent=2)}")
    
    if details:
        print("\nTesting TCAD Neighbors by Street (TANGLEBRIAR)...")
        # Extract street name from address if possible, or just use one
        neighbors = await connector.get_neighbors_by_street("TANGLEBRIAR")
        print(f"Found {len(neighbors)} neighbors.")
        if neighbors:
            print(f"First neighbor: {json.dumps(neighbors[0], indent=2)}")

if __name__ == "__main__":
    asyncio.run(test_tcad())
