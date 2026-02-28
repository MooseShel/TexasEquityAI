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

    logger.info("Fetching properties without embeddings in chunks of 1000...")
    total_updated = 0
    total_batches = 0

    while True:
        # Get up to 1000 properties without embeddings
        response = supabase_service.client.table('properties').select('*').is_('embedding', 'null').limit(1000).execute()
        
        properties = response.data
        if not properties:
            if total_batches == 0:
                logger.info("No properties found missing embeddings.")
            else:
                logger.info(f"Backfill complete! Successfully updated {total_updated} total records.")
            break

        total_batches += 1
        logger.info(f"--- Batch {total_batches} ---")
        logger.info(f"Found {len(properties)} properties to backfill. Calculating vectors...")
        
        batch_success_count = 0
        for prop in properties:
            account_number = prop.get('account_number')
            if not account_number:
                continue
                
            if vector_store.update_property_embedding(account_number, prop):
                batch_success_count += 1
                total_updated += 1
                if batch_success_count % 200 == 0:
                    logger.info(f"  Updated {batch_success_count} / {len(properties)} in current batch...")
                    
        logger.info(f"Finished Batch {total_batches}. Updated {batch_success_count}/{len(properties)} records.")

if __name__ == "__main__":
    backfill()
