import asyncio
import sys
import logging
from backend.agents.district_factory import DistrictConnectorFactory
from backend.agents.tad_connector import TADConnector
from backend.agents.ccad_connector import CCADConnector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def test_tad():
    print("\n--- Testing TAD Connector ---")
    connector = DistrictConnectorFactory.get_connector("TAD")
    assert isinstance(connector, TADConnector)
    
    # 1. Discovery
    print("Searching for neighbors on 'MAIN'...")
    neighbors = await connector.get_neighbors_by_street("MAIN")
    print(f"Found {len(neighbors)} neighbors.")
    
    if neighbors:
        first = neighbors[0]
        print(f"Sample Neighbor: {first}")
        
        # 2. Details
        acc = first['account_number']
        print(f"Fetching details for account {acc}...")
        details = await connector.get_property_details(acc)
        print(f"Details: {details}")
        
        if details:
            assert details['district'] == 'TAD'
            assert 'appraised_value' in details

async def test_ccad():
    print("\n--- Testing CCAD Connector ---")
    connector = DistrictConnectorFactory.get_connector("CCAD")
    assert isinstance(connector, CCADConnector)
    
    # 1. Discovery
    print("Searching for neighbors on 'CLARA'...")
    neighbors = await connector.get_neighbors_by_street("CLARA")
    print(f"Found {len(neighbors)} neighbors.")
    
    if neighbors:
        first = neighbors[0]
        print(f"Sample Neighbor: {first}")
        
        # 2. Details
        acc = first['account_number']
        print(f"Fetching details for account {acc}...")
        details = await connector.get_property_details(acc)
        print(f"Details: {details}")
        
        if details:
            assert details['district'] == 'CCAD'
            assert 'appraised_value' in details

async def main():
    await test_tad()
    await test_ccad()

if __name__ == "__main__":
    asyncio.run(main())
