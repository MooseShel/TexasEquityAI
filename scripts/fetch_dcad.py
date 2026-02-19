import sys, os
sys.path.append(os.getcwd())
from backend.db.supabase_client import supabase_service
# Fetch DCAD residential
res = supabase_service.client.table('properties') \
    .select('account_number, address') \
    .eq('district', 'DCAD') \
    .ilike('address', '%MAIN%') \
    .not_.ilike('address', '%NO TOWN%') \
    .limit(5) \
    .execute()
for r in res.data: print(f"DCAD | {r['account_number']} | {r['address']}")
