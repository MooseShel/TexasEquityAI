#!/usr/bin/env python3
"""
CCAD Bulk Data Import Script
Imports CCAD 2025 property data into Supabase properties table.

Single CSV file — all fields in one row, no joins needed.

Usage:
    python scripts/ccad_bulk_import.py                          # Full import
    python scripts/ccad_bulk_import.py --sample 5000            # First N rows (test)
    python scripts/ccad_bulk_import.py --data-dir CCAD_DATA2024 # Different year
    python scripts/ccad_bulk_import.py --no-overwrite           # Skip existing rows
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
DEFAULT_DATA_DIR = "CCAD_DATA"
DEFAULT_FILENAME = "CCAD_2025.csv"


def parse_number(val: str, default=0):
    """Parse a number that may contain commas (e.g. '3,774')."""
    try:
        return float(str(val).strip().replace(",", "")) if str(val).strip() else default
    except (ValueError, AttributeError):
        return default


def import_ccad_data(sample: int = None, data_dir: str = None, no_overwrite: bool = False):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    client = create_client(url, key)
    logger.info(f"Connected to Supabase: {url}")

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resolved_dir = os.path.join(project_root, data_dir or DEFAULT_DATA_DIR)

    # Try to find the CSV file (may differ by year)
    csv_file = None
    for fname in os.listdir(resolved_dir):
        if fname.upper().endswith(".CSV"):
            csv_file = os.path.join(resolved_dir, fname)
            break

    if not csv_file:
        logger.error(f"No CSV file found in {resolved_dir}")
        sys.exit(1)

    logger.info(f"Data file: {csv_file}")
    logger.info(f"Mode: {'SKIP existing (no-overwrite)' if no_overwrite else 'OVERWRITE existing'}")

    batch = []
    total_read = total_imported = errors = 0

    with open(csv_file, encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip non-real property rows
            if row.get("propType", "").strip().lower() != "real":
                continue

            acct = row.get("propID", "").strip()
            if not acct:
                continue

            total_read += 1

            # Use pre-built address string — clean up double space before city
            address = row.get("situsConcat", "").strip().replace(" , ", ", ")

            appraised = parse_number(row.get("currValAppraised", "0"))
            market    = parse_number(row.get("currValMarket", "0"))
            bld_area  = parse_number(row.get("imprvMainArea", "0"))
            yr_built  = row.get("imprvYearBuilt", "").strip() or None
            nbhd_code = row.get("nbhdCode", "").strip() or None

            record = {
                "account_number":    acct,
                "address":           address,
                "appraised_value":   appraised,
                "market_value":      market if market > 0 else None,
                "building_area":     int(bld_area) if bld_area > 0 else None,
                "year_built":        yr_built,
                "neighborhood_code": nbhd_code,
                "district":          "CCAD",
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
    logger.info("CCAD Import complete!")
    logger.info(f"  Total rows read:    {total_read:,}")
    logger.info(f"  Rows imported:      {total_imported:,}")
    logger.info(f"  Batch errors:       {errors}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import CCAD bulk data into Supabase")
    parser.add_argument("--sample", type=int, default=None, help="Only import first N rows (for testing)")
    parser.add_argument("--data-dir", dest="data_dir", default=None, help="Data directory name relative to project root (default: CCAD_DATA)")
    parser.add_argument("--no-overwrite", dest="no_overwrite", action="store_true", help="Skip rows that already exist in Supabase")
    args = parser.parse_args()

    import_ccad_data(sample=args.sample, data_dir=args.data_dir, no_overwrite=args.no_overwrite)
