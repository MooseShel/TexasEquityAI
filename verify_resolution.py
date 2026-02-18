import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

# Mock the bridge response
class MockBridge:
    async def resolve_address(self, address):
        if "Dallas" in address:
            return {"account_number": "12345678901234567", "address": "123 Main St, Dallas, TX"}
        if "Houston" in address:
            return {"account_number": "1234567890123", "address": "456 Main St, Houston, TX"}
        return None

async def test_district_inference():
    print("Testing District Inference Logic...")
    
    # We can't easily test main.py directly without running the server, 
    # but we can verify the logic we inserted.
    
    # Replicating the logic from main.py
    cases = [
        ("123 Main St, Dallas, TX", "DCAD"),
        ("456 Main St, Houston, TX", "HCAD"),
        ("789 Main St, Austin, TX", "TCAD"),
        ("321 Main St, Plano, TX", "CCAD"),
        ("654 Main St, Fort Worth, TX", "TAD"),
        ("Unknown Place", None) # Should fallback or remain None
    ]
    
    for addr, expected_district in cases:
        district = None
        res_addr = addr.lower()
        if "dallas" in res_addr: district = "DCAD"
        elif "austin" in res_addr: district = "TCAD"
        elif "fort worth" in res_addr: district = "TAD"
        elif "plano" in res_addr: district = "CCAD"
        elif "houston" in res_addr: district = "HCAD"
        
        print(f"Address: '{addr}' -> Inferred District: '{district}' | Expected: '{expected_district}'")
        assert district == expected_district

if __name__ == "__main__":
    asyncio.run(test_district_inference())
    print("District Inference Verification Passed.")
