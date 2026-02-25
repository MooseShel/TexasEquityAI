import os
import sys
import logging
import asyncio

# Setup path so we can import backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.db.supabase_client import supabase_service
from backend.db.vector_store import vector_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backfill():
    if not supabase_service.client:
        logger.error("Supabase client not initialized")
        return

    logger.info("Fetching properties without embeddings...")
    # Get properties without embeddings
    # Pagination might be needed if there are many, but let's try a bulk fetch first
    response = supabase_service.client.table('properties').select('*').is_('embedding', 'null').limit(1000).execute()
    
    properties = response.data
    if not properties:
        logger.info("No properties found missing embeddings.")
        return

    logger.info(f"Found {len(properties)} properties to backfill. Calculating vectors...")
    
    success_count = 0
    for prop in properties:
        account_number = prop.get('account_number')
        if not account_number:
            continue
            
        if vector_store.update_property_embedding(account_number, prop):
            success_count += 1
            if success_count % 100 == 0:
                logger.info(f"Updated {success_count} properties...")
                
    logger.info(f"Backfill complete! Successfully updated {success_count}/{len(properties)} records.")

if __name__ == "__main__":
    backfill()
