"""
Test commercial property enrichment pipeline.
Usage: python test_commercial_enrichment.py
"""
import asyncio
import os
import sys
from dotenv import load_dotenv
from backend.agents.non_disclosure_bridge import NonDisclosureBridge

load_dotenv()

async def debug_rentcast():
    bridge = NonDisclosureBridge()
    # Test the ghost record address string
    addr = "28750 tomball pkwy, Texas, Houston, TX"
    print(f"Checking: '{addr}'")
    try:
        ptype = await bridge.detect_property_type(addr)
        print(f"Property Type: '{ptype}'")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_rentcast())
