import os
import httpx
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Prefer": "count=planned"
}

r = httpx.get(f"{url}/rest/v1/properties?valuation_history=not.is.null&select=account_number&limit=1", headers=headers)
print(f"Approx rows with history: {r.headers.get('content-range', r.text[:200])}")
