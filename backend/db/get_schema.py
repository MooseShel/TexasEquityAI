import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(".env")

from backend.db.supabase_client import SupabaseService

async def run():
    c = SupabaseService()
    res = c.client.table('properties').select('*').limit(1).execute()
    if res.data:
        print("COLUMNS IN PROPERTIES TABLE:")
        for key in res.data[0].keys():
            print(f"- {key}")
    else:
        print("No data found in properties table.")

if __name__ == "__main__":
    asyncio.run(run())
