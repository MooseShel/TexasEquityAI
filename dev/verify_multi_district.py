import asyncio
import sys
import os
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from agents.district_factory import DistrictConnectorFactory

async def verify_connectors():
    factory = DistrictConnectorFactory()
    
    # Test cases
    test_cases = [
        {"district": "TCAD", "account": "177373"}, # Travis
        {"district": "DCAD", "account": "00000776533000000"}, # Dallas (17 digits)
        {"district": "CCAD", "account": "R-4753-00M-0010-1"}, # Collin
        {"district": "TAD", "account": "04657837"}, # Tarrant
        {"district": "TAD", "account": "05762499"}, # Tarrant (Empire Rd)
    ]
    
    for case in test_cases:
        print(f"\n--- Testing {case['district']} (Account: {case['account']}) ---")
        try:
            connector = factory.get_connector(district_code=case['district'])
            print(f"Instantiated: {type(connector).__name__}")
            
            details = await connector.get_property_details(case['account'])
            if details:
                print(f"Successfully fetched details:")
                print(f"  Address: {details.get('address')}")
                print(f"  Market Value: {details.get('market_value')}")
                print(f"  Year Built: {details.get('year_built')}")
                print(f"  Living Area: {details.get('building_area')}")
            else:
                print("Failed to fetch details.")
        except Exception as e:
            print(f"Error testing {case['district']}: {e}")

if __name__ == "__main__":
    asyncio.run(verify_connectors())
