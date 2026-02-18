#!/usr/bin/env python3
"""
DCAD Bulk Data Import Script
Imports DCAD 2025 real property data into Supabase properties table.

Joins three CSV files:
  - ACCOUNT_INFO.CSV       → account number, address, neighborhood code
  - ACCOUNT_APPRL_YEAR.CSV → appraised/market value, state class
  - RES_DETAIL.CSV         → building area, year built

Usage:
    python scripts/dcad_bulk_import.py                               # Import all (2025)
    python scripts/dcad_bulk_import.py --sample 5000                 # First N rows (test)
    python scripts/dcad_bulk_import.py --data-dir DCAD2024           # Different year
    python scripts/dcad_bulk_import.py --no-overwrite                # Skip existing rows
"""

import sys
import os
import csv
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 500
DEFAULT_DATA_DIR = "DCAD2025"


def parse_number(val: str, default=0):
    try:
        return float(str(val).strip()) if str(val).strip() else default
    except (ValueError, AttributeError):
        return default


def build_address(info_row: dict) -> str:
    """Build address from DCAD ACCOUNT_INFO fields."""
    street_num  = info_row.get("STREET_NUM", "").strip()
    half_num    = info_row.get("STREET_HALF_NUM", "").strip()
    street_name = info_row.get("FULL_STREET_NAME", "").strip()
    unit        = info_row.get("UNIT_ID", "").strip()
    city        = info_row.get("PROPERTY_CITY", "").strip()
    zipcode     = info_row.get("PROPERTY_ZIPCODE", "").strip()[:5]  # trim to 5-digit zip

    num_part = f"{street_num}{half_num}" if half_num else street_num
    street_part = f"{num_part} {street_name}".strip()
    if unit:
        street_part += f" #{unit}"
    parts = [p for p in [street_part, city, "TX", zipcode] if p]
    return ", ".join(parts)


def load_lookup(filepath: str, key_col: str, value_cols: list, year_col: str = "APPRAISAL_YR", year: str = "2025") -> dict:
    """Load a CSV into a dict keyed by key_col, filtering to the given appraisal year."""
    result = {}
    with open(filepath, encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if year_col and row.get(year_col, "").strip() != year:
                continue
            acct = row.get(key_col, "").strip()
            if acct:
                result[acct] = {col: row.get(col, "").strip() for col in value_cols}
    logger.info(f"Loaded {len(result):,} rows from {os.path.basename(filepath)}")
    return result


def import_dcad_data(sample: int = None, data_dir: str = None, no_overwrite: bool = False):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    client = create_client(url, key)
    logger.info(f"Connected to Supabase: {url}")

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resolved_dir = os.path.join(project_root, data_dir or DEFAULT_DATA_DIR)

    info_file    = os.path.join(resolved_dir, "ACCOUNT_INFO.CSV")
    apprl_file   = os.path.join(resolved_dir, "ACCOUNT_APPRL_YEAR.CSV")
    res_file     = os.path.join(resolved_dir, "RES_DETAIL.CSV")

    for f in [info_file, apprl_file, res_file]:
        if not os.path.exists(f):
            logger.error(f"Required file not found: {f}")
            sys.exit(1)

    logger.info(f"Data directory: {resolved_dir}")
    logger.info(f"Mode: {'SKIP existing (no-overwrite)' if no_overwrite else 'OVERWRITE existing'}")

    # Load valuation and building data into memory (lookup dicts)
    logger.info("Loading ACCOUNT_APPRL_YEAR (valuations)...")
    apprl = load_lookup(apprl_file, "ACCOUNT_NUM",
                        ["TOT_VAL", "PREV_MKT_VAL", "SPTD_CODE"])

    logger.info("Loading RES_DETAIL (building info)...")
    res = load_lookup(res_file, "ACCOUNT_NUM",
                      ["TOT_LIVING_AREA_SF", "YR_BUILT"])

    # Stream ACCOUNT_INFO as the primary source and join
    logger.info("Streaming ACCOUNT_INFO and building records...")
    batch = []
    total_read = total_imported = errors = 0

    with open(info_file, encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("APPRAISAL_YR", "").strip() != "2025":
                continue

            acct = row.get("ACCOUNT_NUM", "").strip()
            if not acct:
                continue

            total_read += 1

            address = build_address(row)
            nbhd_code = row.get("NBHD_CD", "").strip() or None

            # Join valuation data
            val_data  = apprl.get(acct, {})
            appraised = parse_number(val_data.get("TOT_VAL", "0"))
            market    = parse_number(val_data.get("PREV_MKT_VAL", "0"))

            # Join building data
            res_data  = res.get(acct, {})
            bld_area  = parse_number(res_data.get("TOT_LIVING_AREA_SF", "0"))
            yr_built  = res_data.get("YR_BUILT", "").strip() or None

            record = {
                "account_number":    acct,
                "address":           address,
                "appraised_value":   appraised,
                "market_value":      market if market > 0 else None,
                "building_area":     int(bld_area) if bld_area > 0 else None,
                "year_built":        yr_built,
                "neighborhood_code": nbhd_code,
                "district":          "DCAD",
            }
            record = {k: v for k, v in record.items() if v is not None}
            batch.append(record)
            total_imported += 1

            if len(batch) >= BATCH_SIZE:
                try:
                    if no_overwrite:
                        client.table("properties").upsert(batch, on_conflict="account_number", ignore_duplicates=True).execute()
                    else:
                        client.table("properties").upsert(batch, on_conflict="account_number").execute()
                    logger.info(f"  Upserted batch | total imported: {total_imported:,} | read: {total_read:,}")
                except Exception as e:
                    logger.error(f"  Batch upsert failed: {e}")
                    errors += 1
                batch = []

            if sample and total_imported >= sample:
                logger.info(f"Sample limit reached ({sample} rows).")
                break

    # Flush remaining
    if batch:
        try:
            if no_overwrite:
                client.table("properties").upsert(batch, on_conflict="account_number", ignore_duplicates=True).execute()
            else:
                client.table("properties").upsert(batch, on_conflict="account_number").execute()
            logger.info(f"  Upserted final batch of {len(batch)} rows.")
        except Exception as e:
            logger.error(f"  Final batch upsert failed: {e}")
            errors += 1

    logger.info("=" * 60)
    logger.info("DCAD Import complete!")
    logger.info(f"  Total rows read:    {total_read:,}")
    logger.info(f"  Rows imported:      {total_imported:,}")
    logger.info(f"  Batch errors:       {errors}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import DCAD bulk data into Supabase")
    parser.add_argument("--sample", type=int, default=None, help="Only import first N rows (for testing)")
    parser.add_argument("--data-dir", dest="data_dir", default=None, help="Data directory name relative to project root (default: DCAD2025)")
    parser.add_argument("--no-overwrite", dest="no_overwrite", action="store_true", help="Skip rows that already exist in Supabase")
    args = parser.parse_args()

    import_dcad_data(sample=args.sample, data_dir=args.data_dir, no_overwrite=args.no_overwrite)
