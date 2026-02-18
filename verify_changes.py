import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.utils.address_utils import normalize_address
from backend.main import is_real_address

def test_address_utils():
    print("Testing Address Utils...")
    cases = [
        ("HCAD Account 12345", "12345"),
        ("123 Main St, Houston, TX, Houston, TX", "123 Main St, Houston, TX"),
        ("  HCAD Account 999  ", "999"),
        ("Real Address 123", "Real Address 123"),
    ]
    
    for inp, expected in cases:
        result = normalize_address(inp)
        print(f"Input: '{inp}' -> Output: '{result}' | Match: {result == expected}")
        assert result == expected

if __name__ == "__main__":
    test_address_utils()
    print("Address Utils Verification Passed.")
