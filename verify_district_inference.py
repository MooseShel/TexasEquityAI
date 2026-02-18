import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.agents.district_factory import DistrictConnectorFactory

def test_account_inference():
    print("Testing Account Number District Inference...")
    
    cases = [
        ("0123456789012", "HCAD"),        # 13 digits
        ("12345678901234567", "DCAD"),    # 17 chars
        ("R123456", "CCAD"),              # Starts with R
        ("r987654", "CCAD"),              # lowercase r
        ("123456", None),                 # Short/Unknown
        ("", None),                       # Empty
        (None, None)                      # None
    ]
    
    for acc, expected in cases:
        result = DistrictConnectorFactory.detect_district_from_account(acc)
        print(f"Account: '{acc}' -> Detected: '{result}' | Expected: '{expected}'")
        assert result == expected

if __name__ == "__main__":
    test_account_inference()
    print("Account Inference Verification Passed.")
