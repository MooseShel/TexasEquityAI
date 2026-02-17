import os
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

async def check_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    print(f"URL: {url}")
    print(f"Key: {key[:10]}...")
    
    if not url or not key:
        print("Missing Supabase credentials")
        return

    try:
        client: Client = create_client(url, key)
        print("Client created successfully")
        
        # Check properties table
        try:
            response = client.table("properties").select("*").limit(1).execute()
            print("Table 'properties' exists and is accessible")
        except Exception as e:
            print(f"Error accessing 'properties' table: {e}")
            print("HINT: Did you run the SQL script in the Supabase SQL Editor?")

    except Exception as e:
        print(f"Failed to connect to Supabase: {e}")

if __name__ == "__main__":
    asyncio.run(check_supabase())
