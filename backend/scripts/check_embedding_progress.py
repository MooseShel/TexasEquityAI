import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

if not url or not key:
    print("Error: Missing SUPABASE_URL or SUPABASE_KEY in environment.")
    sys.exit(1)

supabase: Client = create_client(url, key)

try:
    print("Querying database statistics by district...")
    
    # Get total properties by district
    res_districts = supabase.table("properties").select("district").execute()
    
    # We can't do exact count group by easily with the basic client, so we'll do an exact count
    # per district if we know the unique districts. Usually HCAD and BCAD.
    
    districts = ["HCAD", "BCAD"]
    
    print("\n--- Embedding Progress By County ---")
    
    total_all = 0
    embedded_all = 0

    for d in districts:
        # Get total for district
        t_res = supabase.table("properties").select("account_number", count="planned").eq("district", d).limit(1).execute()
        t_count = t_res.count or 0
        total_all += t_count
        
        # Get embedded for district
        e_res = supabase.table("properties").select("account_number", count="planned").eq("district", d).not_.is_("embedding", "null").limit(1).execute()
        e_count = e_res.count or 0
        embedded_all += e_count
        
        if t_count > 0:
            pct = (e_count / t_count) * 100
            print(f"\n{d} TOTAL:    ~{t_count:,}")
            print(f"{d} Embedded: ~{e_count:,} ({pct:.2f}%)")
            print(f"{d} Remaining:  ~{t_count - e_count:,}")
        else:
            print(f"\n{d}: No properties found.")

    if total_all > 0:
        pct_all = (embedded_all / total_all) * 100
        print(f"\n--- OVERALL TOTAL ---")
        print(f"Total Properties: ~{total_all:,}")
        print(f"Total Embedded:   ~{embedded_all:,} ({pct_all:.2f}%)")

except Exception as e:
    print(f"Error querying Supabase: {e}")
