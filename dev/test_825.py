import asyncio
from backend.agents.property_type_resolver import resolve_property_type

async def main():
    ptype, source = await resolve_property_type(
        account_number="",  # Just use address
        address="825 Town and Country Ln, Houston, TX",
        district="HCAD"
    )
    print(f"Property Type: {ptype}, Source: {source}")

if __name__ == "__main__":
    asyncio.run(main())
