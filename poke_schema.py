import asyncio
from backend.db.supabase_client import supabase_service

async def poke_schema():
    if not supabase_service.client:
        print("Supabase client not initialized.")
        return
    try:
        res = supabase_service.client.table("properties").select("*").limit(1).execute()
        if res.data:
            print(f"Columns: {res.data[0].keys()}")
        else:
            print("No data in properties table.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(poke_schema())
