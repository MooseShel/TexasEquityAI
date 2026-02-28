import asyncio
from backend.db.vector_store import vector_store
from backend.db.supabase_client import supabase_service

async def check():
    prop = await supabase_service.get_property_by_account('0660460450034')
    if not prop:
        print('No property found')
        return
    
    print(f"Subject: {prop.get('address')}")
    print(f"  nbhd={prop.get('neighborhood_code')}, area={prop.get('building_area')}, year={prop.get('year_built')}")
    
    # Test pgvector search
    results = vector_store.find_similar_properties(prop, limit=40)
    print(f"\nPgvector returned: {len(results)} matches")
    
    subj_nbhd_base = str(prop.get('neighborhood_code', '')).split('.')[0]
    local = [r for r in results if str(r.get('neighborhood_code', '')).split('.')[0] == subj_nbhd_base]
    citywide = [r for r in results if str(r.get('neighborhood_code', '')).split('.')[0] != subj_nbhd_base]
    
    print(f"Local (nbhd {subj_nbhd_base}): {len(local)}")
    print(f"City-wide: {len(citywide)}")
    
    print("\nLocal comps:")
    for r in local[:5]:
        print(f"  {r.get('account_number')} | {r.get('address')} | area={r.get('building_area')} | val={r.get('appraised_value')} | sim={r.get('similarity', '?')}")
    
    print("\nCity-wide comps (first 5):")
    for r in citywide[:5]:
        print(f"  {r.get('account_number')} | {r.get('address')} | nbhd={r.get('neighborhood_code')} | area={r.get('building_area')} | val={r.get('appraised_value')} | sim={r.get('similarity', '?')}")

asyncio.run(check())
