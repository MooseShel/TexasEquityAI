import asyncio
import os
import sys
from dotenv import load_dotenv
import logging

# Setup basic logging to see what's happening
logging.basicConfig(level=logging.INFO)

# Ensure backend acts as root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env variables
load_dotenv(".env")

from backend.db.supabase_client import SupabaseService

async def run():
    print("Initializing Supabase Client...")
    c = SupabaseService()
    
    print("Clearing ALL protests...")
    try:
        c.client.table('protests').delete().neq('account_number', '000000').execute()
        print("✅ All protests cleared.")
    except Exception as e:
        print(f"Error clearing protests: {e}")

    print("Clearing ALL property caches...")
    try:
        # Fetch all account numbers that have cached comps
        res = c.client.table('properties').select('account_number').not_.is_("cached_comps", "null").execute()
        
        accounts = [row['account_number'] for row in res.data]
        print(f"Found {len(accounts)} properties with cached comps.")
        
        for acct in accounts:
            c.client.table('properties').update({
                'cached_comps': None, 
                'comps_scraped_at': None
            }).eq('account_number', acct).execute()
            
        print("✅ All property caches cleared.")
    except Exception as e:
        print(f"Error clearing property caches: {e}")
        
    print("Clearing ALL equity comparables history...")
    try:
        c.client.table('equity_comparables').delete().neq('account_number', '000000').execute()
        print("✅ Equity comparables history cleared.")
    except Exception as e:
        print(f"Error clearing equity comparables: {e}")

    print("Clearing ALL sales comparables history...")
    try:
        c.client.table('sales_comparables').delete().neq('account_number', '000000').execute()
        print("✅ Sales comparables history cleared.")
    except Exception as e:
        print(f"Error clearing sales comparables: {e}")

    print("DONE!")

if __name__ == "__main__":
    asyncio.run(run())
