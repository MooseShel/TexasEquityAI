import requests
import json
import time

def test_protest_enrichment(address_query):
    print(f"--- Running Stress Test for: {address_query} ---")
    
    # 1. Start timer
    start_time = time.time()
    
    # 2. Call API with streaming
    url = f"http://localhost:8000/protest/{address_query}"
    
    flood_zone = "N/A"
    permit_status = "N/A"
    narrative_snippet = ""
    comparables = []
    final_subject_address = ""
    
    try:
        with requests.get(url, stream=True) as r:
            for line in r.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode('utf-8'))
                        
                        # Print status updates
                        if "status" in data:
                            print(f"[STATUS] {data['status']}")
                            
                        # Capture final data
                        if "data" in data:
                            prop = data['data'].get('property', {})
                            final_subject_address = prop.get('address', 'Unknown')
                            flood_zone = prop.get('flood_zone', 'N/A')
                            permit_status = prop.get('permit_summary', {}).get('status', 'N/A')
                            
                            equity = data['data'].get('equity', {})
                            comparables = [c.get('address') for c in equity.get('equity_5', [])]
                            
                            narrative_snippet = data['data'].get('narrative', '')
                            
                            print(f"\nReport Generated at: {data['data'].get('form_path')}")
                            
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        print(f"Error: {e}")

    # 3. Analyze Results
    print("\n\n--- FINAL VERIFICATION RESULTS ---")
    
    # Address Cleaning Check
    print(f"Subject Address: '{final_subject_address}'")
    if "HCAD Account" in final_subject_address:
        print(" [FAIL] Address still contains 'HCAD Account'")
    else:
        print(" [PASS] Address is clean.")

    # Comparables Uniqueness Check
    print("\nComparables Found:")
    unique_comps = set()
    for c in comparables:
        print(f" - {c}")
        unique_comps.add(c)
    
    if len(unique_comps) < len(comparables):
        print(f" [FAIL] Duplicate comparables found! ({len(unique_comps)} unique out of {len(comparables)})")
    elif len(unique_comps) == 0:
        print(" [WARN] No comparables found.")
    else:
        print(f" [PASS] All {len(unique_comps)} comparables are unique.")
        
    # Subject Exclusion Check
    if any(final_subject_address in c for c in unique_comps):
         print(" [FAIL] Subject property found in comparables list!")
    else:
         print(" [PASS] Subject property excluded from comparables.")

    # Enrichment Check
    print(f"\nFEMA Flood Zone: {flood_zone}")
    print(f"Permit Status: {permit_status}")
    
    print("\nNarrative Keyword Check:")
    keywords = ['flood', 'permit', 'renovation', 'obsolescence', 'condition']
    for k in keywords:
        if k in narrative_snippet.lower():
            print(f" [PASS] Narrative cites: '{k}'")
        else:
            print(f" [MISSING] Narrative does NOT cite: '{k}'")

    print(f"\nTotal Test Time: {time.time() - start_time:.2f}s")
    
if __name__ == "__main__":
    # Test with the specific flood-prone address
    test_protest_enrichment("5100 Jackwood St, Houston, TX 77096")
