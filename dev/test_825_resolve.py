import asyncio
from dotenv import load_dotenv
load_dotenv()

from backend.db.supabase_client import supabase_service
from backend.agents.non_disclosure_bridge import NonDisclosureBridge

async def main():
    bridge = NonDisclosureBridge()
    
    # Test resolve_account_id with the exact input
    print("=== resolve_account_id ===")
    result = await bridge.resolve_account_id("825 Town and Country Ln, Houston, TX")
    print(f"Result: {result}")
    
    if result:
        print(f"\n=== get_property_by_account({result['account_number']}) ===")
        prop = await supabase_service.get_property_by_account(result['account_number'])
        if prop:
            for k in ['account_number', 'address', 'appraised_value', 'building_area', 'neighborhood_code', 'state_class', 'year_built']:
                print(f"  {k}: {prop.get(k)}")
        else:
            print("  Not found")
    else:
        print("FAILED: resolve_account_id returned None")

if __name__ == "__main__":
    asyncio.run(main())
