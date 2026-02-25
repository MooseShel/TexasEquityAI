import asyncio
from backend.db.supabase_client import supabase_service

async def run():
    print("Testing get_neighbors_from_db for '8401', building_area=2500")
    # Using 935 Lamonte properties: let's query the specific code
    
    # Let me first get the property to see its building area
    prop = await supabase_service.get_property_by_account('0660460450034')
    if prop:
        print(f"Property found: {prop.get('address')} Nbhd: {prop.get('neighborhood_code')} Area: {prop.get('building_area')}")
        area = int(prop.get('building_area', 0))
        code = prop.get('neighborhood_code')
        results = await supabase_service.get_neighbors_from_db('0660460450034', code, area)
        print(f"Neighbors found: {len(results)}")
        for r in results:
            print(f" - {r.get('account_number')} | {r.get('address')} | Nbhd: {r.get('neighborhood_code')} | Area: {r.get('building_area')}")
    else:
        print("Property not found!")

if __name__ == "__main__":
    asyncio.run(run())
