import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from backend.db.supabase_client import supabase_service

async def main():
    result = supabase_service.client.table("properties").select("account_number, address, appraised_value, building_area, neighborhood_code, state_class, year_built, market_value, district, land_area, building_grade").eq("account_number", "1281720010011").execute()
    if result.data:
        rec = result.data[0]
        print("=== Key Fields ===")
        for k, v in sorted(rec.items()):
            print(f"  {k}: {v}")
    else:
        print("No record found")

if __name__ == "__main__":
    asyncio.run(main())
