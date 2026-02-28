import asyncio
import sys
from backend.agents.district_factory import DistrictConnectorFactory

async def test():
    conn = DistrictConnectorFactory.get_connector('TCAD')
    street_target = sys.argv[1] if len(sys.argv) > 1 else 'Caudill'
    
    print(f"Testing bare street: '{street_target}'...")
    n1 = await conn.get_neighbors_by_street(street_target)
    print(f"'{street_target}' neighbors found:", len(n1) if n1 else 0)

asyncio.run(test())
