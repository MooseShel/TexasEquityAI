import asyncio
import os
import sys
import random

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.supabase_client import supabase_service

async def fetch_samples():
    districts = ['HCAD', 'DCAD', 'TAD', 'TCAD', 'CCAD']
    
    print(f"{'DISTRICT':<8} | {'ACCOUNT NUMBER':<20} | {'ADDRESS':<40} | {'TYPE (Guess)':<10}")
    print("-" * 90)

    for dist in districts:
        try:
            # Fetch 3 residential (mid-range value, valid address)
            res = supabase_service.client.table('properties') \
                .select('*') \
                .eq('district', dist) \
                .gt('appraised_value', 300000) \
                .lt('appraised_value', 1000000) \
                .ilike('address', '% %') \
                .not_.ilike('address', '%MINERAL%') \
                .not_.ilike('address', '%TELECOM%') \
                .not_.ilike('address', '%FIBER%') \
                .not_.ilike('address', '%EQUIP%') \
                .not_.ilike('address', '%PIPELINE%') \
                .not_.ilike('address', '%NO TOWN%') \
                .not_.ilike('account_number', '99%') \
                .limit(50) \
                .execute()
            
            if res.data:
                samples = random.sample(res.data, min(3, len(res.data)))
                for s in samples:
                    addr = s.get('address', 'Unknown').replace('\n', ' ').strip()
                    print(f"{dist:<8} | {s.get('account_number', ''):<20} | {addr:<50} | Residential ({s.get('appraised_value', 0):,.0f})")

            # Fetch 1 likely commercial (very high value)
            comm_res = supabase_service.client.table('properties') \
                .select('*') \
                .eq('district', dist) \
                .gt('appraised_value', 5000000) \
                .limit(20) \
                .execute()

            if comm_res.data:
                comm_sample = random.sample(comm_res.data, 1)[0]
                addr = comm_sample.get('address', 'Unknown').replace('\n', ' ').strip()
                print(f"{dist:<8} | {comm_sample.get('account_number', ''):<20} | {addr:<50} | Commercial? ({comm_sample.get('appraised_value', 0):,.0f})")
            else:
                 print(f"{dist:<8} | {'(No high val found)':<20} | {'':<50} | Commercial?")
                 
        except Exception as e:
            print(f"Error fetching {dist}: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_samples())
