import os
import sys
import logging
import json

# Setup path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.db.supabase_client import supabase_service
from backend.db.vector_store import vector_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_search():
    if not supabase_service.client:
        logger.error("Supabase client not initialized")
        return

    response = supabase_service.client.table('properties').select('*').eq('account_number', '1177890010035').execute()
    
    if not response.data:
        logger.error("No properties found.")
        return

    subject = response.data[0]

    logger.info(f"Subject Property: {subject['address']} (Area: {subject.get('building_area')}, Year: {subject.get('year_built')})")
    
    logger.info("Running vector similarity search...")
    results = vector_store.find_similar_properties(subject, limit=5)
    
    if not results:
        logger.error("No similar properties found.")
        return
        
    for i, r in enumerate(results):
        logger.info(f"Match {i+1}: {r['address']} | Similarity: {r['similarity']:.4f} | Area: {r['building_area']} | Year: {r['year_built']}")

if __name__ == "__main__":
    test_search()
