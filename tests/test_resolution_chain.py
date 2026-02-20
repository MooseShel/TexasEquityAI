"""
tests/test_resolution_chain.py
Tests the ID-first address resolution chain:
  DB → RentCast → RealEstateAPI → normalized scraper fallback
"""
import asyncio
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ── Unit tests for normalize_address_for_search ──────────────────────────────

def test_normalize():
    from backend.utils.address_utils import normalize_address_for_search

    cases = [
        # (input, expected_substring)
        ("123 N Oak St, Houston TX",      "North Oak Street"),
        ("456 S Main Ave",                "South Main Avenue"),
        ("7823 Bellfort St Suite 100",    "Bellfort Street"),    # suite stripped
        ("28750 Tomball Pkwy # 5",        "Tomball Parkway"),   # unit stripped
        ("1234 NW Freeway Apt B",         "Northwest Freeway"), # direction + unit
    ]
    all_pass = True
    for raw, expected in cases:
        result = normalize_address_for_search(raw)
        ok = expected.lower() in result.lower()
        status = "✅" if ok else "❌"
        print(f"  {status} '{raw}' → '{result}'  (expected to contain '{expected}')")
        if not ok:
            all_pass = False
    return all_pass


# ── Integration test for resolve_account_id ──────────────────────────────────

async def test_resolve_chain():
    from backend.agents.non_disclosure_bridge import NonDisclosureBridge
    bridge = NonDisclosureBridge()

    test_addresses = [
        # Address,                             Expected district
        ("7823 Bellfort St, Houston TX",        "HCAD"),  # known residential
        ("28750 Tomball Pkwy, Houston TX",       None),    # commercial — may need RealEstateAPI
    ]

    all_pass = True
    for address, expected_district in test_addresses:
        print(f"\n  Testing: '{address}'")
        result = await bridge.resolve_account_id(address)
        if result:
            acc    = result.get('account_number')
            dist   = result.get('district')
            source = result.get('source')
            conf   = result.get('confidence', 0)
            ok_dist = (expected_district is None) or (dist == expected_district)
            ok_acc  = bool(acc and len(acc) > 4)
            status = "✅" if (ok_acc and ok_dist) else "⚠️"
            print(f"  {status} Resolved → account='{acc}' district='{dist}' source={source} confidence={conf:.0%}")
            if not ok_acc:
                print(f"      ❌ Account ID looks invalid: '{acc}'")
                all_pass = False
            if not ok_dist:
                print(f"      ❌ Expected district '{expected_district}', got '{dist}'")
                all_pass = False
        else:
            print(f"  ⚠️  No account ID found — chain exhausted (may be expected for unindexed commercial)")

    return all_pass


async def main():
    print("\n" + "="*60)
    print("1. normalize_address_for_search() — unit tests")
    print("="*60)
    norm_ok = test_normalize()

    print("\n" + "="*60)
    print("2. resolve_account_id() — integration tests")
    print("="*60)
    chain_ok = await test_resolve_chain()

    print("\n" + "="*60)
    overall = "✅ ALL PASSED" if (norm_ok and chain_ok) else "⚠️  SOME ISSUES — check logs above"
    print(f"Result: {overall}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
