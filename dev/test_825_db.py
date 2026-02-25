import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from backend.db.supabase_client import supabase_service
from backend.agents.non_disclosure_bridge import NonDisclosureBridge

async def main():
    address = "825 Town and Country Ln"
    print(f"Testing address: {address}")
    
    # 1. Check RentCast
    print("\n--- Testing RentCast ---")
    bridge = NonDisclosureBridge()
    try:
        rc_type = await bridge.detect_property_type(f"{address}, Houston, TX")
        print(f"RentCast detect_property_type: {rc_type}")
    except Exception as e:
        print(f"RentCast error: {e}")

    # 2. Check DB
    print("\n--- Testing DB ---")
    try:
        # We don't have account number, let's search by address if possible
        # Supabase service might not have search_by_address, let's just query directly
        result = supabase_service.client.table("properties").select("account_number, state_class, address").ilike("address", f"%{address}%").execute()
        print(f"DB results for address: {result.data}")
    except Exception as e:
        print(f"DB error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
