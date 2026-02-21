#!/usr/bin/env python3
"""
Import historical HCAD valuation data into the valuation_history JSON field.

Reads real_acct.txt from multiple years (2022, 2023, 2024) and merges
valuation data into the existing properties.valuation_history column.

Each file contains current year AND prior year values, giving us:
  - 2022 file → 2022 + 2021 values
  - 2023 file → 2023 + 2022 values  (reinforces)
  - 2024 file → 2024 + 2023 values  (reinforces)

Usage:
    python scripts/import_hcad_history.py
"""

import os, sys, json, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 500
DATA_BASE = r"C:\Users\Husse\Downloads\Data\HCAD"

# Column indices in real_acct.txt (tab-delimited)
COL_ACCT = 0
COL_YR = 1
COL_LAND_VAL = 43
COL_BLD_VAL = 44
COL_TOT_APPR = 48
COL_TOT_MKT = 49
COL_PRIOR_LAND = 50
COL_PRIOR_BLD = 51
COL_PRIOR_APPR = 54
COL_PRIOR_MKT = 55


def safe_float(val):
    try:
        return float(str(val).strip().replace(",", "")) if val else 0
    except:
        return 0


def parse_year_file(filepath, year_label):
    """
    Parse a real_acct.txt file and return dict of account -> {year: valuation_data}.
    Each record yields current year and prior year data.
    """
    accounts = {}  # acct -> {year: {appraised, market, land_appraised, improvement}}
    
    with open(filepath, "r", encoding="latin-1") as f:
        header = f.readline()  # skip header
        for line_num, line in enumerate(f, start=2):
            cols = line.strip().split("\t")
            if len(cols) < 56:
                continue
            
            acct = cols[COL_ACCT].strip()
            if not acct:
                continue
            
            # Current year values
            yr = cols[COL_YR].strip() or year_label
            appr = safe_float(cols[COL_TOT_APPR])
            mkt = safe_float(cols[COL_TOT_MKT])
            land = safe_float(cols[COL_LAND_VAL])
            bld = safe_float(cols[COL_BLD_VAL])
            
            if acct not in accounts:
                accounts[acct] = {}
            
            # Store current year data (only if there's meaningful data)
            if appr > 0 or mkt > 0:
                accounts[acct][yr] = {
                    "appraised": appr,
                    "market": mkt,
                    "land_appraised": land,
                    "improvement": bld,
                }
            
            # Store prior year data
            prior_appr = safe_float(cols[COL_PRIOR_APPR])
            prior_mkt = safe_float(cols[COL_PRIOR_MKT])
            prior_land = safe_float(cols[COL_PRIOR_LAND])
            prior_bld = safe_float(cols[COL_PRIOR_BLD])
            
            if prior_appr > 0 or prior_mkt > 0:
                prior_yr = str(int(yr) - 1) if yr.isdigit() else ""
                if prior_yr:
                    # Only set prior if we don't already have a more authoritative value
                    if prior_yr not in accounts[acct]:
                        accounts[acct][prior_yr] = {
                            "appraised": prior_appr,
                            "market": prior_mkt,
                            "land_appraised": prior_land,
                            "improvement": prior_bld,
                        }
    
    return accounts


def merge_and_upload(sb, all_accounts):
    """Merge all years and batch-update valuation_history in Supabase."""
    total = 0
    batch = []
    
    for acct, years_data in all_accounts.items():
        if not years_data:
            continue
        
        # Convert to JSON string for Supabase JSONB
        batch.append({
            "account_number": acct,
            "valuation_history": years_data,
        })
        total += 1
        
        if len(batch) >= BATCH_SIZE:
            try:
                sb.table("properties").upsert(
                    batch, on_conflict="account_number"
                ).execute()
            except Exception as e:
                logger.warning(f"Batch error: {e}")
            batch = []
            if total % 50000 == 0:
                logger.info(f"  {total:,} records processed")
    
    if batch:
        try:
            sb.table("properties").upsert(
                batch, on_conflict="account_number"
            ).execute()
        except Exception as e:
            logger.warning(f"Final batch error: {e}")
    
    return total


def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set")
        sys.exit(1)
    sb = create_client(url, key)
    
    logger.info("=" * 60)
    logger.info("  HCAD HISTORICAL VALUATION IMPORT")
    logger.info("=" * 60)
    
    # Process files in chronological order (oldest first so newer data overwrites)
    years = ["2022", "2023", "2024"]
    all_accounts = {}  # acct -> {year: data}
    
    for yr in years:
        filepath = os.path.join(DATA_BASE, yr, "real_acct.txt")
        if not os.path.exists(filepath):
            logger.warning(f"File not found: {filepath}")
            continue
        
        logger.info(f"Processing {yr}: {filepath}")
        year_accounts = parse_year_file(filepath, yr)
        logger.info(f"  Parsed {len(year_accounts):,} accounts from {yr}")
        
        # Merge into all_accounts
        for acct, years_data in year_accounts.items():
            if acct not in all_accounts:
                all_accounts[acct] = {}
            all_accounts[acct].update(years_data)
    
    logger.info(f"\nTotal unique accounts: {len(all_accounts):,}")
    
    # Show a sample
    sample_acct = "0660460360030"
    if sample_acct in all_accounts:
        logger.info(f"Sample ({sample_acct}): {json.dumps(all_accounts[sample_acct], indent=2)}")
    
    # Upload
    logger.info("\nUploading to Supabase...")
    total = merge_and_upload(sb, all_accounts)
    
    logger.info("=" * 60)
    logger.info(f"Complete! Updated {total:,} records with valuation history.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
