import requests
import json

def test_houston_permits():
    print("--- Testing City of Houston Permit API (CKAN) ---")
    # Base URL for Houston Open Data CKAN API
    # Approved Building Permits Resource ID (example from public docs)
    resource_id = "8729584b-013b-410a-85d8-4f8a42e74e64" 
    url = "https://data.houstontx.gov/api/3/action/datastore_search"
    
    params = {
        "resource_id": resource_id,
        "q": "935 Lamonte", # Search term
        "limit": 5
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                records = data['result']['records']
                print(f"Success! Found {len(records)} permit records for '935 Lamonte'.")
                for r in records:
                    print(f" - Date: {r.get('permit_issue_date')}, Type: {r.get('description')}, Val: ${r.get('declared_valuation')}")
            else:
                print("API returned success=False")
        else:
            print(f"Failed with Status Code: {response.status_code}")
    except Exception as e:
        print(f"Error testing Permits API: {e}")

def test_fema_flood_api():
    print("\n--- Testing FEMA Flood Map Service (ArcGIS REST) ---")
    # FEMA NFHL MapServer
    # We query the 'identify' endpoint for the 'Flood Hazard Zones' layer (layer 28 usually)
    # Using coords for Lamonte Ln area (~29.83, -95.44)
    url = "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/identify"
    
    params = {
        "geometry": "-95.4485,29.8325", # Long, Lat
        "geometryType": "esriGeometryPoint",
        "sr": "4324",
        "layers": "all",
        "tolerance": "3",
        "mapExtent": "-95.45,29.83,-95.44,29.84",
        "imageDisplay": "1280,800,96",
        "returnGeometry": "false",
        "f": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            if results:
                print(f"Success! Found {len(results)} GIS features for coordinates.")
                for res in results:
                    if res['layerName'] == 'Flood Hazard Zones':
                        print(f" - Flood Zone detected: {res['attributes'].get('FLD_ZONE')}")
            else:
                print("No results found for these coordinates.")
        else:
            print(f"Failed with Status Code: {response.status_code}")
    except Exception as e:
        print(f"Error testing FEMA API: {e}")

if __name__ == "__main__":
    test_houston_permits()
    test_fema_flood_api()
