import requests
import json

def test_ccad():
    # Dataset ID for 2025 CCAD data (potentially)
    dataset_id = "vffy-snc6"
    # url = f"https://data.austintexas.gov/resource/{dataset_id}.json?$limit=1"
    url = f"https://data.texas.gov/resource/{dataset_id}.json?$limit=1"
    
    print(f"Querying: {url}")
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        print("Response Code:", resp.status_code)
        if data:
            print(json.dumps(data[0], indent=2))
        else:
            print("No data returned.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ccad()
