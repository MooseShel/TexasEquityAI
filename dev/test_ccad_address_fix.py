"""Test CCAD connector with address-as-account fix and Google geocoder."""
import asyncio
import logging
import os
import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

async def test_ccad_address_fix():
    from backend.agents.ccad_connector import CCADConnector
    
    connector = CCADConnector()
    address = "1500 Charleston Dr, Plano, TX"
    
    print(f"\n=== Test 1: get_property_details with address-as-account ===")
    print(f"Input: '{address}'")
    details = await connector.get_property_details(address)
    if details:
        print(f"✅ Found! Account: {details.get('account_number')}")
        print(f"   Address: {details.get('address')}")
        print(f"   Value: ${details.get('appraised_value',0):,.0f}")
        print(f"   Area: {details.get('building_area',0)} sqft")
    else:
        print("❌ Not found in Socrata dataset")
    
    print(f"\n=== Test 2: search_by_address ===")
    result = await connector.search_by_address(address)
    if result:
        print(f"✅ Found! Account: {result.get('account_number')}")
        print(f"   Address: {result.get('address')}")
    else:
        print("❌ Not found")
    
    await connector.client.aclose()

def test_google_geocoder():
    api_key = os.getenv("GOOGLE_STREET_VIEW_API_KEY")
    if not api_key:
        print("\n⚠️ No Google API key found — skipping geocoder test")
        return
    
    address = "1500 Charleston Dr, Plano, TX"
    print(f"\n=== Test 3: Google Geocoding for '{address}' ===")
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": api_key},
            timeout=5,
        )
        data = resp.json()
        if data.get("status") == "OK" and data.get("results"):
            loc = data["results"][0]["geometry"]["location"]
            print(f"✅ lat={loc['lat']}, lon={loc['lng']}")
            print(f"   formatted: {data['results'][0].get('formatted_address')}")
        else:
            print(f"❌ Status: {data.get('status')}, Error: {data.get('error_message', 'none')}")
    except Exception as e:
        print(f"💥 Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ccad_address_fix())
    test_google_geocoder()
