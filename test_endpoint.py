import requests
import json
import time

def test_backend():
    account = "0660460360030"
    url = f"http://localhost:8000/protest/{account}"
    print(f"Calling backend: {url}")
    try:
        start_time = time.time()
        response = requests.get(url, timeout=120)
        end_time = time.time()
        print(f"Status Code: {response.status_code}")
        print(f"Time taken: {end_time - start_time:.2f} seconds")
        
        if response.status_code == 200:
            data = response.json()
            print("SUCCESS! Data received.")
            print(f"Address: {data['property']['address']}")
            print(f"Appraised Value: {data['property']['appraised_value']}")
        else:
            print(f"FAILED: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_backend()
