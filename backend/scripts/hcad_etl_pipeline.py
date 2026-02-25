import os
import zipfile
import urllib.request
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
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Missing Supabase credentials. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# HCAD Data Configuration
HCAD_FTP_URL = "https://pdata.hcad.org/download/2024/Real_acct.zip" # Placeholder for actual URL
DOWNLOAD_DIR = "/tmp/hcad_data"
CHUNK_SIZE = 5000

def download_and_extract(url: str, extract_to: str) -> bool:
    """Downloads the HCAD data zip and extracts it."""
    os.makedirs(extract_to, exist_ok=True)
    zip_path = os.path.join(extract_to, "hcad_data.zip")
    
    try:
        logger.info(f"Downloading HCAD data from {url}...")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
            out_file.write(response.read())
        
        logger.info(f"Extracting {zip_path}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        return True
    except Exception as e:
        logger.error(f"Failed to download or extract HCAD data: {e}")
        return False

async def upsert_properties_chunk(records: List[Dict]):
    """Upserts a chunk of property records to Supabase."""
    try:
        # Avoid crashing on conflict by letting Supabase handle it natively
        data, count = supabase.table("properties").upsert(records, on_conflict="account_number").execute()
        return len(data[1]) if data else 0
    except Exception as e:
        logger.error(f"Failed to upsert chunk: {e}")
        return 0

async def process_hcad_data(data_dir: str):
    """
    Parses HCAD txt/csv extracts, normalizes them, and streams to Supabase.
    Expects 'real_acct.txt' and 'building_res.txt' to exist in data_dir.
    """
    acct_file = os.path.join(data_dir, "real_acct.txt")
    bldg_res_file = os.path.join(data_dir, "building_res.txt")
    
    if not os.path.exists(acct_file):
        logger.warning(f"File {acct_file} not found. Ensure the extract contains this file.")
        return
        
    logger.info("Starting ETL process for HCAD properties...")
    
    total_processed = 0
    
    # Process account data in chunks to prevent multi-GB memory spikes
    # HCAD data is usually tab-separated or comma-separated. Using \t assumption here.
    try:
        for chunk in pd.read_csv(acct_file, sep='\t', chunksize=CHUNK_SIZE, encoding='latin1', low_memory=False, on_bad_lines='skip'):
            records_to_upsert = []
            
            for _, row in chunk.iterrows():
                # HCAD specific parsing (adjust column indexes/names based on actual HCAD extract dict)
                account_num = str(row.get('ACCT', row.iloc[0])).zfill(13) if pd.notna(row.get('ACCT', row.iloc[0])) else None
                if not account_num or str(account_num) == 'nan': continue
                
                # Normalize address parts safely
                try: num = str(row.get('STR_NUM', row.iloc[1] if len(row) > 1 else '')).split('.')[0]
                except: num = ''
                try: name = str(row.get('STR_NAME', row.iloc[2] if len(row) > 2 else ''))
                except: name = ''
                
                address = f"{num} {name}".strip()
                
                owner = str(row.get('OWNER_NAME', row.iloc[3] if len(row) > 3 else '')).strip()
                nbhd = str(row.get('NBHD', row.iloc[4] if len(row) > 4 else '')).strip()
                
                try: app_val = float(row.get('APPRAISED_VAL', 0) or 0)
                except: app_val = 0
                try: mkt_val = float(row.get('MARKET_VAL', 0) or 0)
                except: mkt_val = 0
                try: land_val = float(row.get('LAND_VAL', 0) or 0)
                except: land_val = 0
                
                record = {
                    "account_number": account_num,
                    "district": "HCAD",
                    "address": address,
                    "owner_name": owner,
                    "appraised_value": app_val,
                    "market_value": mkt_val,
                    "land_value": land_val,
                    "neighborhood_code": nbhd,
                    "last_updated": pd.Timestamp.now().isoformat()
                }
                records_to_upsert.append(record)
            
            if records_to_upsert:
                # Upsert to Supabase
                success_count = await upsert_properties_chunk(records_to_upsert)
                total_processed += len(records_to_upsert)
                logger.info(f"Upserted chunk of {len(records_to_upsert)} records. Total: {total_processed}")
                
    except Exception as e:
        logger.error(f"Error processing HCAD chunk: {e}")
        
    logger.info(f"HCAD ETL pipeline completed. Processed {total_processed} properties.")

async def main():
    logger.info("Running Weekly HCAD ETL Pipeline...")
    
    # Recommended flow for production via GitHub Actions:
    # if download_and_extract(HCAD_FTP_URL, DOWNLOAD_DIR):
    #     await process_hcad_data(DOWNLOAD_DIR)
    
    # For local execution testing:
    test_dir = "./hcad_extract"
    if not os.path.exists(test_dir):
        logger.info(f"No local data found at {test_dir}. Run with actual FTP download or add mock extracts.")
    else:
        await process_hcad_data(test_dir)

if __name__ == "__main__":
    asyncio.run(main())
