
import asyncio
import os
from dotenv import load_dotenv
import requests
import json

load_dotenv()

def check_rentcast():
    api_key = os.getenv("RENTCAST_API_KEY")
    base_url = "https://api.rentcast.io/v1/properties"
    
    address = "935 Lamonte Ln, Houston, TX 77018"
    
    headers = {"X-Api-Key": api_key, "accept": "application/json"}
    params = {"address": address}
    
    print(f"Querying RentCast for: {address}")
    try:
        response = requests.get(base_url, headers=headers, params=params)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                print("First result keys:", data[0].keys())
                print(json.dumps(data[0], indent=2))
            else:
                print("No data found.")
        else:
            print("Error:", response.text)
    except Exception as e:
        print("Exception:", e)

if __name__ == "__main__":
    check_rentcast()
