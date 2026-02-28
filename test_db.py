import asyncio
from backend.db.supabase_client import supabase_service

async def check():
    res = supabase_service.client.table('properties').select('account_number, address, neighborhood_code, building_area, year_built, embedding').eq('neighborhood_code', '1635.09').execute()
    data = res.data
    print(f"Total properties in 1635.09: {len(data)}")
    if data:
        with_embed = sum(1 for d in data if d.get('embedding'))
        print(f"Properties with calculated pgvector embeddings: {with_embed}")
        print("Sample comp:")
        print(data[0])

if __name__ == "__main__":
    asyncio.run(check())
