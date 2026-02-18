def auto_detect_district(raw_acc):
    if not raw_acc:
        return None
        
    clean_acc = raw_acc.replace("-", "").replace(" ", "").strip()
    target_district = None

    # 17 characters -> DCAD
    if len(clean_acc) == 17:
        target_district = "DCAD"
    # 13 digits -> HCAD
    elif len(clean_acc) == 13 and clean_acc.isdigit():
        target_district = "HCAD"
    # Starts with R -> CCAD
    elif raw_acc.upper().strip().startswith("R"):
        target_district = "CCAD"
    
    # TCAD: Usually 6 digits (up to 7)
    elif len(clean_acc) <= 7 and clean_acc.isdigit():
        target_district = "TCAD"
        
    # TAD: 8 digits
    elif len(clean_acc) == 8 and clean_acc.isdigit():
        target_district = "TAD"
    
    # Address-based inference (Simple keywords)
    elif any(c.isalpha() for c in raw_acc):
        lower_acc = raw_acc.lower()
        if "dallas" in lower_acc: target_district = "DCAD"
        elif "austin" in lower_acc: target_district = "TCAD"
        elif "fort worth" in lower_acc: target_district = "TAD"
        elif "plano" in lower_acc: target_district = "CCAD"
        elif "houston" in lower_acc: target_district = "HCAD"
        
    return target_district

def test_logic():
    cases = [
        ("0123456789012", "HCAD"),        # 13 digits
        ("12345678901234567", "DCAD"),    # 17 chars
        ("R123456", "CCAD"),              # CCAD
        ("r999", "CCAD"),                 # CCAD lower
        ("123456", "TCAD"),               # TCAD (6 digits)
        ("1234567", "TCAD"),              # TCAD (7 digits)
        ("12345678", "TAD"),              # TAD (8 digits)
        ("123 Main St, Austin, TX", "TCAD"),
        ("456 Forth Worth Ave", "TAD"),   # Typo in string "Forth" might fail if logic looks for "Fort Worth"
        ("456 Fort Worth Ave", "TAD")
    ]
    
    for inp, expected in cases:
        result = auto_detect_district(inp)
        print(f"Input: '{inp}' -> Detected: '{result}' | Expected: '{expected}'")
        if expected:
            assert result == expected

if __name__ == "__main__":
    test_logic()
    print("Frontend Logic Verification Passed.")
