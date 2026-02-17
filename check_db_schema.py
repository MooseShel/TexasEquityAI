import asyncio
import os
from backend.db.supabase_client import supabase_service

async def check_schema():
    print("Checking database for 'neighborhood_code' support...")
    test_data = {
        "account_number": "TEST999999",
        "address": "123 Test St",
        "neighborhood_code": "8101.01"
    }
    try:
        result = await supabase_service.upsert_property(test_data)
        if result and 'neighborhood_code' in result:
            print("✅ Database supports 'neighborhood_code' column.")
        elif result:
            print("❌ Database upsert worked but 'neighborhood_code' not returned. Checking all keys...")
            print(f"Keys returned: {result.keys()}")
        else:
            print("❌ Upsert returned no data.")
    except Exception as e:
        print(f"❌ Database error: {e}")
        if "neighborhood_code" in str(e):
            print("   -> Tip: neighborhood_code column probably missing.")

if __name__ == "__main__":
    asyncio.run(check_schema())
