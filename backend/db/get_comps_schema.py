import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(".env")

from backend.db.supabase_client import SupabaseService

async def run():
    c = SupabaseService()
    # Execute raw sql or use RPC, wait, supabase JS doesn't have an easy way.
    # We can query information_schema but maybe not directly via REST API.
    # Let's try inserting a dummy row with an invalid column to see the error message which might reveal the schema,
    # OR better yet, just look at how 'equity_comparables' is structured and assume they are similar.
    # Actually, we can just insert a dummy row like {'id': 1} and see if it works.
    try:
        res = c.client.table('sales_comparables').insert({}).execute()
        print(res.data)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run())
