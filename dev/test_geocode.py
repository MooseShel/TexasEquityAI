"""Quick test to check Nominatim geocoding for different address formats."""
import requests
import time

queries = [
    "1500 Charleston Dr, Plano, TX",
    "1500 Charleston Drive, Plano, TX",  
    "1500 Charleston Dr, Plano, Texas",
    "1500 Charleston, Plano, TX",
    "1500 Charleston Drive, Plano, Texas, USA",
    "1500 Charleston Dr, Plano, TX 75075",  # with ZIP
]

for q in queries:
    time.sleep(1.1)  # Nominatim rate limit
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 1},
            headers={"User-Agent": "TexasEquityAI/1.0"},
            timeout=10,
        )
        data = resp.json()
        if data:
            print(f"✅ '{q}' -> lat={data[0]['lat']}, lon={data[0]['lon']}")
        else:
            print(f"❌ '{q}' -> NO RESULTS")
    except Exception as e:
        print(f"💥 '{q}' -> ERROR: {e}")
