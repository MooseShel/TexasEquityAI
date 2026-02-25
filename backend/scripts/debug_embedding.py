import os, sys, logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from backend.db.supabase_client import supabase_service
from backend.db.vector_store import vector_store

logging.basicConfig(level=logging.INFO)

def run():
    # fetch one record
    resp = supabase_service.client.table('properties').select('account_number, building_area, embedding').limit(1).execute()
    prop = resp.data[0]
    acc = prop['account_number']
    print(f'Original [{acc}]: Area={prop.get("building_area")} Embedding={str(prop.get("embedding"))[:50]}')
    
    vec = vector_store.compute_embedding(prop)
    emb_str = f"[{','.join(f'{x:.4f}' for x in vec)}]"
    print(f"Computed str: {emb_str}")
    
    update_resp = supabase_service.client.table('properties').update({'embedding': emb_str}).eq('account_number', acc).execute()
    print(f"Update response data: {update_resp.data}")
    
    refetch = supabase_service.client.table('properties').select('account_number, embedding').eq('account_number', acc).execute()
    print(f"Refetched [{acc}] Embedding={str(refetch.data[0].get('embedding'))[:50]}")

run()
