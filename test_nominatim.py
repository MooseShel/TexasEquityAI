import requests

address = '8100 Washington Ave'
resp = requests.get(
    'https://nominatim.openstreetmap.org/search',
    params={'q': address, 'format': 'json', 'addressdetails': 1, 'limit': 5},
    headers={'User-Agent': 'TexasEquityAI/1.0'}
)
print("Results:", [f"{r.get('display_name')}" for r in resp.json()])
