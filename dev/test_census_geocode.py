"""Test US Census Bureau geocoder as fallback for Nominatim."""
import requests

address = "1500 Charleston Dr, Plano, TX"
print(f"Testing Census geocoder for: {address}")

try:
    resp = requests.get(
        "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
        params={
            "address": address,
            "benchmark": "Public_AR_Current",
            "format": "json",
        },
        timeout=10,
    )
    data = resp.json()
    matches = data.get("result", {}).get("addressMatches", [])
    print(f"Matches: {len(matches)}")
    for m in matches:
        coords = m["coordinates"]
        print(f"  lat={coords['y']}, lon={coords['x']}")
        print(f"  matched: {m.get('matchedAddress', '')}")
except Exception as e:
    print(f"Error: {e}")
