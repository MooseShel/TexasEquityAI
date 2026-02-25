import asyncio
from backend.db.supabase_client import supabase_service

async def test():
    try:
        comps = await supabase_service.get_neighbors_from_db('0660460450034', '8014', 3748, 'HCAD')
        print(f"Returned comps: {len(comps)}")
    except Exception as e:
        print(f'Error: {e}')

asyncio.run(test())
