import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from backend.db.supabase_client import supabase_service
from backend.db.vector_store import vector_store

async def update_neighborhood():
    logger.info("Fetching properties in 1635.09...")
    res = supabase_service.client.table('properties').select('*').eq('neighborhood_code', '1635.09').is_('embedding', 'null').execute()
    
    properties = res.data
    logger.info(f"Found {len(properties)} properties missing embeddings in 1635.09.")
    
    # Run concurrently for speed
    async def process_prop(prop):
        # vector_store is synchronous, so we run it in a thread
        account_number = prop.get('account_number')
        if account_number:
            return await asyncio.to_thread(vector_store.update_property_embedding, account_number, prop)
        return False

    if properties:
        tasks = [process_prop(p) for p in properties]
        results = await asyncio.gather(*tasks)
        
        success = sum(1 for r in results if r)
        logger.info(f"Successfully computed embeddings for {success} properties in 1635.09!")

if __name__ == "__main__":
    asyncio.run(update_neighborhood())
