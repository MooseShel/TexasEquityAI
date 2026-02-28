import asyncio
from backend.agents.equity_agent import EquityAgent
from backend.db.supabase_client import supabase_service

async def fetch_lamonte():
    print("Fetching 843 Lamonte Ln (Account: 0660460360030)")
    prop = await supabase_service.get_property_by_account('0660460360030')
    if not prop:
        print("Property not found!")
        return
        
    print("Fetching neighborhood fallback comps from DB...")
    neighborhood_comps = await supabase_service.get_neighbors_from_db(
        prop.get('account_number'), 
        prop.get('neighborhood_code', '8014.00'), 
        prop.get('building_area', 1000)
    )

    print("Initializing EquityAgent...")
    agent = EquityAgent()
    print("Calling find_equity_5...")
    result = agent.find_equity_5(prop, neighborhood_comps)
    
    print("\n--- RESULTS ---")
    comps = result.get('equity_5', [])
    if not comps:
        print("No comps returned.")
    else:
        for c in comps:
            sim = c.get('similarity') or c.get('similarity_score')
            print(f"{c.get('address')} | Similarity raw: {sim} | Distance: {c.get('distance')} | Area: {c.get('building_area')}")

if __name__ == "__main__":
    asyncio.run(fetch_lamonte())
