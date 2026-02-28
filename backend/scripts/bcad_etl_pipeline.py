import os
import pandas as pd
import logging
import asyncio
from typing import List, Dict

from dotenv import load_dotenv
from supabase import create_client, Client

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Missing Supabase credentials. Ensure SUPABASE_URL and SUPABASE_KEY are set.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

CHUNK_SIZE = 1000

# Fixed-width column specifications for APPRAISAL_INFO.TXT
# Format: (col_name, start_index, end_index) - note that pd.read_fwf expects (start, end) where start is 0-indexed
BCAD_INFO_COLS = [
    ('prop_id', 0, 12),
    ('geo_id', 546, 596),
    ('py_owner_name', 608, 678),
    ('situs_street_prefx', 1039, 1049),
    ('situs_street', 1049, 1099),
    ('situs_street_suffix', 1099, 1109),
    ('situs_city', 1109, 1139),
    ('situs_zip', 1139, 1149),
    ('hood_cd', 1685, 1695),
    ('land_hstd_val', 1795, 1810),
    ('land_non_hstd_val', 1810, 1825),
    ('imprv_hstd_val', 1825, 1840),
    ('imprv_non_hstd_val', 1840, 1855),
    ('appraised_val', 1915, 1930),
    ('market_value', 4213, 4227),
    ('situs_num', 4459, 4474),
    ('situs_unit', 4474, 4479),
]

def clean_str(val):
    if pd.isna(val): return ""
    return str(val).strip()

def clean_float(val):
    if pd.isna(val): return 0.0
    try:
        return float(val)
    except:
        return 0.0

async def upsert_properties_chunk(records: List[Dict]):
    """Upserts a chunk of property records to Supabase."""
    try:
        # We assume the API can handle conflicts based on constraints
        data, count = supabase.table("properties").upsert(records, on_conflict="account_number").execute()
        return len(data[1]) if data else 0
    except Exception as e:
        logger.error(f"Failed to upsert chunk: {e}")
        return 0

async def process_bcad_data(data_dir: str, dry_run=False):
    """
    Parses BCAD fixed-width extracts, normalizes them, and streams to Supabase.
    Expects '2025-07-25_003206_APPRAISAL_INFO.TXT' to exist in data_dir.
    """
    # Look for the appraisal info file, the exact name might vary slightly by date so we find it programmatically
    appraisal_files = [f for f in os.listdir(data_dir) if "APPRAISAL_INFO.TXT" in f]
    if not appraisal_files:
        logger.warning(f"No APPRAISAL_INFO.TXT file found in {data_dir}.")
        return

    acct_file = os.path.join(data_dir, appraisal_files[0])
    logger.info(f"Starting ETL process for BCAD properties using {acct_file}...")
    
    total_processed = 0
    
    colspecs = [(start, end) for _, start, end in BCAD_INFO_COLS]
    names = [name for name, _, _ in BCAD_INFO_COLS]
    
    try:
        # Read in chunks to prevent memory issues for 2GB+ file
        for chunk in pd.read_fwf(acct_file, colspecs=colspecs, names=names, chunksize=CHUNK_SIZE, encoding='latin1'):
            records_to_upsert = []
            
            for _, row in chunk.iterrows():
                account_num = clean_str(row['prop_id']).zfill(12) if clean_str(row['prop_id']) else None
                if not account_num: continue
                
                # Construct address
                s_num = clean_str(row['situs_num'])
                s_dir = clean_str(row['situs_street_prefx'])
                s_name = clean_str(row['situs_street'])
                s_type = clean_str(row['situs_street_suffix'])
                s_unit = clean_str(row['situs_unit'])
                
                address_parts = [s_num, s_dir, s_name, s_type]
                address = " ".join([p for p in address_parts if p]).strip()
                if s_unit and s_unit.lower() != 'nan':
                    address += f" UNIT {s_unit}"
                
                owner = clean_str(row['py_owner_name'])
                nbhd = clean_str(row['hood_cd'])
                
                app_val = clean_float(row['appraised_val'])
                mkt_val = clean_float(row['market_value'])
                land_val = clean_float(row['land_hstd_val']) + clean_float(row['land_non_hstd_val'])
                
                # Only insert if address has something useful or if values are present
                if not address and app_val == 0.0:
                    continue
                
                record = {
                    "account_number": account_num,
                    "district": "BCAD",
                    "address": address,
                    "appraised_value": app_val,
                    "market_value": mkt_val,
                    "neighborhood_code": nbhd,
                    "last_scraped_at": pd.Timestamp.now().isoformat()
                }
                records_to_upsert.append(record)
            
            if dry_run:
                logger.info(f"DRY RUN: Found {len(records_to_upsert)} valid records in chunk.")
                if records_to_upsert:
                    logger.info(f"Sample dry run record: {records_to_upsert[0]}")
                break # Only run one chunk in dry-run
                
            if records_to_upsert:
                # Upsert to Supabase
                success_count = await upsert_properties_chunk(records_to_upsert)
                total_processed += len(records_to_upsert)
                logger.info(f"Upserted chunk of {len(records_to_upsert)} records. Total: {total_processed}")
                
    except Exception as e:
        logger.error(f"Error processing BCAD chunk: {e}")
        
    logger.info(f"BCAD ETL pipeline completed. Processed {total_processed} properties.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BCAD ETL Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Run but don't commit to Supabase")
    parser.add_argument("--dir", type=str, default=r"C:\Users\Husse\Downloads\Data\BCAD", help="Path to BCAD export txt files")
    args = parser.parse_args()
    
    asyncio.run(process_bcad_data(args.dir, dry_run=args.dry_run))
