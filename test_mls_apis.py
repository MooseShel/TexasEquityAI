import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def test_rentcast_listings(address: str):
    print(f"\n{'='*50}")
    print(f"TESTING RENTCAST /v1/listings/sale FOR: {address}")
    print(f"{'='*50}")
    
    api_key = os.getenv("RENTCAST_API_KEY")
    if not api_key:
        print("Error: RENTCAST_API_KEY not found in .env")
        return
        
    url = "https://api.rentcast.io/v1/listings/sale"
    headers = {"X-Api-Key": api_key, "accept": "application/json"}
    # Search by zip code to ensure we get some listings
    params = {"zipCode": "77018", "status": "Active,Pending,Sold", "limit": 3}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if not data:
                print("No listings found for this address in RentCast.")
            else:
                print(f"Found {len(data)} listing record(s).")
                for i, listing in enumerate(data):
                    print(f"\n--- Listing {i+1} ---")
                    # Look for description-like fields
                    desc_fields = {k: v for k, v in listing.items() if 'desc' in k.lower() or 'remark' in k.lower() or 'text' in k.lower() or k in ['features', 'propertyType']}
                    print("Potential description fields:")
                    print(json.dumps(desc_fields, indent=2))
                    
                    # Print all top-level keys just to see what's available
                    print("\nAll available keys:")
                    print(", ".join(listing.keys()))
        else:
            print(f"Error Response: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

def test_realestate_api(address: str):
    print(f"\n{'='*50}")
    print(f"TESTING REALESTATEAPI /PropertyDetail FOR: {address}")
    print(f"{'='*50}")
    
    api_key = os.getenv("REALESTATEAPI_KEY")
    if not api_key:
        print("Error: REALESTATEAPI_KEY not found in .env")
        return
        
    url = "https://api.realestateapi.com/v2/PropertyDetail"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    payload = {"address": address}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if not data or 'data' not in data:
                print("No data found for this address in RealEstateAPI.")
            else:
                data_obj = data['data']
                if isinstance(data_obj, list):
                    if len(data_obj) > 0:
                        prop = data_obj[0]
                    else:
                        print("Empty data list.")
                        return
                else:
                    prop = data_obj # It's a dict
                    
                print(f"Found property record.")
                
                # Look for description-like fields
                desc_fields = {k: v for k, v in prop.items() if 'desc' in k.lower() or 'remark' in k.lower() or 'mls' in k.lower() or 'text' in k.lower()}
                print("\nPotential description/MLS fields:")
                print(json.dumps(desc_fields, indent=2))
                
                # Check for publicRemarks specifically
                print(f"\nExact 'publicRemarks' field exists? {'publicRemarks' in prop}")
                if 'publicRemarks' in prop:
                    print(f"Value: {prop['publicRemarks']}")
                    
                # Print all top-level keys just to see what's available
                print("\nAll available keys:")
                print(", ".join(prop.keys()))
        else:
            print(f"Error Response: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    # Test with a recently sold property or active listing to maximize chances of finding MLS data
    # Let's use a known Houston address
    test_address = "935 Lamonte Ln, Houston, TX 77018"
    
    print("Testing API capabilities for MLS listing descriptions...")
    test_rentcast_listings(test_address)
    test_realestate_api(test_address)
