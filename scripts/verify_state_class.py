"""Check specific properties and commercial count."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
from backend.agents.property_type_resolver import classify_state_class

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Check known commercial properties
print("=== KNOWN COMMERCIAL PROPERTIES ===")
for acct, name in [("1343220010001", "1125 W Cavalcade"), ("0562460000009", "2414 Mimosa Dr")]:
    r = sb.table("properties").select("state_class,address").eq("account_number", acct).execute()
    if r.data:
        sc = r.data[0].get("state_class") or "NULL"
        addr = r.data[0].get("address", "")
        resolved = classify_state_class(sc) if sc != "NULL" else "Unknown"
        print(f"  {name:<20} state_class={sc:<6} -> {resolved}  ({addr})")
    else:
        print(f"  {name:<20} NOT FOUND IN DB")

# Commercial count
r = sb.table("properties").select("account_number", count="exact").like("state_class", "F%").execute()
print(f"\nF-prefix (Commercial Real): {r.count:,}")

# Sample 5 commercial properties
r = sb.table("properties").select("account_number,address,state_class").like("state_class", "F%").limit(5).execute()
print("\nSample commercial records:")
for d in r.data:
    print(f"  {d['account_number']} | {d.get('state_class','')} | {d.get('address','')}")
