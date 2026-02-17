
import requests
import json

def test_address_search():
    # Simulate user input address
    input_address = "935 Lamonte Ln"
    print(f"Testing Address Search: {input_address}")
    
    url = f"http://localhost:8000/protest/{input_address}"
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            account = data['property'].get('account_number')
            market_val = data.get('market_value')
            
            print("SUCCESS! Data received.")
            print(f"Resolved Account: {account}")
            print(f"Market Value: {market_val}")
            
            if account == "0660460450034" and market_val > 1000000:
                print("PASS: Correctly resolved to target account with real market data.")
            else:
                print("FAIL: Data mismatch.")
        else:
            print(f"FAILED: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_address_search()
