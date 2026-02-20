"""
Test commercial property enrichment pipeline.
Usage: python test_commercial_enrichment.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from backend.agents.commercial_enrichment_agent import CommercialEnrichmentAgent
from backend.agents.non_disclosure_bridge import NonDisclosureBridge

TEST_ADDRESS = "28750 Tomball Pkwy, Tomball, TX 77375"

async def main():
    agent = CommercialEnrichmentAgent()
    bridge = NonDisclosureBridge()

    print(f"\n{'='*60}")
    print(f"Testing Commercial Enrichment for: {TEST_ADDRESS}")
    print(f"{'='*60}\n")

    # 1. Property type gate
    print("1. detect_property_type() via NonDisclosureBridge...")
    prop_type = await bridge.detect_property_type(TEST_ADDRESS)
    print(f"   → propertyType: {prop_type!r}")
    assert prop_type != "Single Family", "Expected commercial/None, got Single Family!"

    # 2. Enrich property
    print("\n2. enrich_property()...")
    enriched = await agent.enrich_property(TEST_ADDRESS)
    if enriched:
        print(f"   → address:        {enriched.get('address')}")
        print(f"   → appraised_value: ${enriched.get('appraised_value', 0):,.0f}")
        print(f"   → building_area:  {enriched.get('building_area', 0):,} sqft")
        print(f"   → year_built:     {enriched.get('year_built')}")
        print(f"   → property_type:  {enriched.get('property_type')}")
        print(f"   → source:         {enriched.get('source')}")
        has_data = enriched.get('appraised_value', 0) > 0 or enriched.get('building_area', 0) > 0
        print(f"\n   ✅ Enrichment has usable data: {has_data}")
    else:
        print("   ⚠️  enrich_property() returned None — API keys may be missing or address not found.")

    # 3. Equity comp pool
    print("\n3. get_equity_comp_pool()...")
    property_details = {
        "address": TEST_ADDRESS,
        "appraised_value": enriched.get('appraised_value', 0) if enriched else 0,
        "building_area": enriched.get('building_area', 0) if enriched else 0,
        "property_type": "commercial",
        "district": "HCAD",
    }
    pool = agent.get_equity_comp_pool(TEST_ADDRESS, property_details)
    print(f"   → Comp pool size: {len(pool)}")
    if pool:
        print(f"   → First comp: {pool[0]}")
        for item in pool:
            assert 'appraised_value' in item, f"Missing appraised_value in comp: {item}"
            assert 'building_area' in item, f"Missing building_area in comp: {item}"
        print(f"   ✅ All comps have required keys (appraised_value, building_area)")
    else:
        print("   ⚠️  No comps returned. SalesAgent APIs may have no data for this address.")

    print(f"\n{'='*60}")
    print("Test complete.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    asyncio.run(main())
