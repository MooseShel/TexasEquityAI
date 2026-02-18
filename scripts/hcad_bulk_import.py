#!/usr/bin/env python3
"""
HCAD Bulk Data Import Script
Imports 2025 HCAD real property data into Supabase properties table.

Usage:
    python scripts/hcad_bulk_import.py                                   # Import 2025 residential
    python scripts/hcad_bulk_import.py --sample 5000                     # Import first N rows (test)
    python scripts/hcad_bulk_import.py --all                             # Import all property types
    python scripts/hcad_bulk_import.py --data-dir hcad_data_2024 --all  # Import 2024 data

Data source: hcad_2025_data/real_acct.txt
"""

import sys
import os
import argparse
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hcad_2025_data")
REAL_ACCT_FILE = os.path.join(DATA_DIR, "real_acct.txt")

# Residential state class codes (A = single family, B = multi-family, etc.)
RESIDENTIAL_CLASSES = {"A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4"}

BATCH_SIZE = 500  # Rows per Supabase upsert batch


def parse_number(val: str, default=0):
    try:
        return float(val.strip()) if val.strip() else default
    except (ValueError, AttributeError):
        return default


def build_address(row: dict) -> str:
    """Build a clean address string from HCAD fields."""
    street = row.get("site_addr_1", "").strip()
    city   = row.get("site_addr_2", "").strip()
    zipcode = row.get("site_addr_3", "").strip()
    parts = [p for p in [street, city, "TX", zipcode] if p]
    return ", ".join(parts)


def is_residential(state_class: str, include_all: bool = False) -> bool:
    if include_all:
        return True
    sc = state_class.strip().upper()
    return sc[:2] in RESIDENTIAL_CLASSES or sc.startswith("A") or sc.startswith("B")


def import_hcad_data(sample: int = None, include_all: bool = False, data_dir: str = None):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    client = create_client(url, key)
    logger.info(f"Connected to Supabase: {url}")

    # Resolve data directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resolved_dir = os.path.join(project_root, data_dir) if data_dir else os.path.join(project_root, "hcad_2025_data")
    real_acct_file = os.path.join(resolved_dir, "real_acct.txt")

    if not os.path.exists(real_acct_file):
        logger.error(f"Data file not found: {real_acct_file}")
        logger.error(f"Expected directory: {resolved_dir}")
        sys.exit(1)

    logger.info(f"Reading {real_acct_file} ...")
    logger.info(f"Mode: {'ALL property types' if include_all else 'Residential only (A/B class)'}")
    if sample:
        logger.info(f"Sample mode: first {sample} matching rows")

    batch = []
    total_read = 0
    total_imported = 0
    total_skipped = 0
    errors = 0

    with open(real_acct_file, "r", encoding="latin-1") as f:
        header = f.readline().strip().split("\t")
        logger.info(f"Columns ({len(header)}): {header[:10]}...")

        for line in f:
            row = dict(zip(header, line.strip().split("\t")))
            total_read += 1

            # Filter by property type
            state_class = row.get("state_class", "").strip()
            if not is_residential(state_class, include_all):
                total_skipped += 1
                continue

            # Skip rows with no appraised value and no address
            acct = row.get("acct", "").strip()
            if not acct:
                total_skipped += 1
                continue

            address = build_address(row)
            appraised = parse_number(row.get("tot_appr_val", "0"))
            market    = parse_number(row.get("tot_mkt_val", "0"))
            bld_ar    = parse_number(row.get("bld_ar", "0"))
            yr_impr   = row.get("yr_impr", "").strip() or None
            nbhd_code = row.get("Neighborhood_Code", "").strip() or None

            record = {
                "account_number":    acct,
                "address":           address,
                "appraised_value":   appraised,
                "market_value":      market if market > 0 else None,
                "building_area":     int(bld_ar) if bld_ar > 0 else None,
                "year_built":        yr_impr,
                "neighborhood_code": nbhd_code,
                "district":          "HCAD",
            }
            # Remove None values
            record = {k: v for k, v in record.items() if v is not None}
            batch.append(record)
            total_imported += 1

            # Flush batch
            if len(batch) >= BATCH_SIZE:
                try:
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
            client.table("properties").upsert(batch, on_conflict="account_number").execute()
            logger.info(f"  Upserted final batch of {len(batch)} rows.")
        except Exception as e:
            logger.error(f"  Final batch upsert failed: {e}")
            errors += 1

    logger.info("=" * 60)
    logger.info(f"Import complete!")
    logger.info(f"  Total rows read:     {total_read:,}")
    logger.info(f"  Rows imported:       {total_imported:,}")
    logger.info(f"  Rows skipped:        {total_skipped:,}")
    logger.info(f"  Batch errors:        {errors}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import HCAD 2025 bulk data into Supabase")
    parser.add_argument("--sample", type=int, default=None, help="Only import first N rows (for testing)")
    parser.add_argument("--all", dest="include_all", action="store_true", help="Include all property types (not just residential)")
    parser.add_argument("--data-dir", dest="data_dir", default=None, help="Data directory name relative to project root (default: hcad_2025_data)")
    args = parser.parse_args()

    import_hcad_data(sample=args.sample, include_all=args.include_all, data_dir=args.data_dir)
