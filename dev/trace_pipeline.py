"""Trace the full pipeline for a given address to identify where equity fallback occurs."""
import asyncio
import sys
sys.path.insert(0, r"c:\Users\Husse\Documents\TexasEquityAI")

from backend.db.supabase_client import supabase_service

async def trace(addr="843 Lamonte Ln"):
    print(f"=== Tracing pipeline for: {addr} ===\n")

    # Step 1: Address Resolution
    candidates = await supabase_service.search_address_globally(addr)
    print("STEP 1: search_address_globally")
    if not candidates:
        print("  NO CANDIDATES FOUND — pipeline dies here.")
        return
    best = candidates[0]
    acct = best.get("account_number")
    dist = best.get("district")
    print(f"  account={acct}  district={dist}")
    print(f"  address={best.get('address')}")
    search_keys = list(best.keys())
    print(f"  Keys in search result: {search_keys}")
    print(f"  neighborhood_code in search result: {best.get('neighborhood_code')}")
    print(f"  building_area in search result: {best.get('building_area')}")

    # Step 2: get_property_by_account
    print("\nSTEP 2: get_property_by_account")
    prop = await supabase_service.get_property_by_account(acct)
    if not prop:
        print("  NO PROPERTY FOUND — pipeline dies here.")
        return
    print(f"  neighborhood_code: {prop.get('neighborhood_code')}")
    print(f"  building_area: {prop.get('building_area')}")
    print(f"  appraised_value: {prop.get('appraised_value')}")
    print(f"  year_built: {prop.get('year_built')}")
    print(f"  district: {prop.get('district')}")

    # Step 3: Ghost check
    print("\nSTEP 3: _is_ghost_record simulation")
    val = float(prop.get("appraised_value") or 0)
    area = float(prop.get("building_area") or 0)
    has_year = bool(prop.get("year_built"))
    has_nbhd = bool(prop.get("neighborhood_code"))
    is_mock = val == 450000.0 and area == 2500.0 and not has_year and not has_nbhd
    is_stub = val <= 1.0 and area <= 1.0
    is_ghost = is_mock or is_stub
    print(f"  val={val}  area={area}  has_year={has_year}  has_nbhd={has_nbhd}")
    print(f"  is_ghost={is_ghost}")

    # Step 4: DB-first cache check
    print("\nSTEP 4: DB-first cache eligibility")
    has_addr = bool(prop.get("address"))
    has_val = bool(prop.get("appraised_value"))
    would_cache = has_addr and has_val and not is_ghost
    print(f"  has_address={has_addr}  has_appraised={has_val}  not_ghost={not is_ghost}")
    print(f"  --> Would use DB cache: {would_cache}")

    # Step 5: Equity lookup
    print("\nSTEP 5: Equity DB comp lookup")
    nbhd = prop.get("neighborhood_code")
    bld = int(prop.get("building_area") or 0)
    print(f"  nbhd_code={nbhd}  bld_area={bld}")
    can_query = bool(nbhd and bld > 0)
    print(f"  --> Can query DB for comps: {can_query}")

    if can_query:
        comps = await supabase_service.get_neighbors_from_db(acct, nbhd, bld, district="HCAD")
        print(f"  DB comps returned: {len(comps)}")
        if len(comps) >= 3:
            print("  --> SUCCESS: Would use DB comps (no live scrape needed)")
        else:
            print("  --> FAIL: < 3 comps — would fall back to live scraping")
        for c in comps[:5]:
            print(f"    {c.get('account_number')} | {c.get('address', '')[:40]} | area={c.get('building_area')} | val={c.get('appraised_value')}")
    else:
        print("  --> FAIL: Missing nbhd_code or bld_area — skips DB, goes to live scraping")

asyncio.run(trace())
