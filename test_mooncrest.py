import asyncio
import logging
import json
from backend.db.supabase_client import supabase_service
from backend.agents.equity_agent import EquityAgent

logging.basicConfig(level=logging.INFO)

async def test_mooncrest():
    print("Fetching 1311040030008...")
    prop = await supabase_service.get_property_by_account('1311040030008')
    if not prop:
        print("Property not found in Supabase!")
        return
        
    print(f"Subject: {prop.get('address')} | Nbhd: {prop.get('neighborhood_code')} | Area: {prop.get('building_area')} | Year: {prop.get('year_built')}")
    
    agent = EquityAgent()
    # Mock finding comps to trigger the logging from equity_agent.py
    res = agent.find_equity_5(prop, [])
    
    print("\n--- RESULTS ---")
    print(f"Found {len(res.get('equity_5', []))} comps.")
    for i, comp in enumerate(res.get('equity_5', [])):
        print(f"{i+1}. {comp.get('address')} | Nbhd: {comp.get('neighborhood_code')} | Source: {comp.get('comp_source')} | Year: {comp.get('year_built')} | Val: ${comp.get('appraised_value')}")

if __name__ == "__main__":
    asyncio.run(test_mooncrest())
