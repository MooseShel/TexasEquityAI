#!/usr/bin/env python3
"""
TAD Bulk Data Import Script
Imports TAD (Tarrant Appraisal District) property data into Supabase properties table.

Single pipe-delimited .txt file with all fields.

Usage:
    python scripts/tad_bulk_import.py                          # Full import
    python scripts/tad_bulk_import.py --sample 5000            # First N rows (test)
    python scripts/tad_bulk_import.py --data-dir TAD_2024      # Different year
    python scripts/tad_bulk_import.py --no-overwrite           # Skip existing rows
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 500
DEFAULT_DATA_DIR = "TAD_2025"


def parse_number(val: str, default=0):
    try:
        return float(str(val).strip()) if str(val).strip() and str(val).strip() != '0' else default
    except (ValueError, AttributeError):
        return default


def build_address(row: dict) -> str:
    """Build address from TAD fields."""
    situs = row.get("Situs_Address", "").strip()
    if not situs:
        return ""
    # Owner_CityState is like "FT WORTH, TX" — extract city
    owner_cs = row.get("Owner_CityState", "").strip()
    zip_code = row.get("Owner_Zip", "").strip()[:5]
    # Normalize Fort Worth city name
    city = owner_cs.split(",")[0].strip() if "," in owner_cs else ""
    parts = [p for p in [situs, city, "TX", zip_code] if p]
    return ", ".join(parts)


def import_tad_data(sample: int = None, data_dir: str = None, no_overwrite: bool = False):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    client = create_client(url, key)
    logger.info(f"Connected to Supabase: {url}")

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resolved_dir = os.path.join(project_root, data_dir or DEFAULT_DATA_DIR)

    # Find the .txt file
    txt_file = None
    for fname in os.listdir(resolved_dir):
        if fname.lower().endswith(".txt"):
            txt_file = os.path.join(resolved_dir, fname)
            break

    if not txt_file:
        logger.error(f"No .txt file found in {resolved_dir}")
        sys.exit(1)

    logger.info(f"Data file: {txt_file}")
    logger.info(f"Mode: {'SKIP existing (no-overwrite)' if no_overwrite else 'OVERWRITE existing'}")

    batch = []
    total_read = total_imported = total_skipped = errors = 0

    with open(txt_file, encoding="latin-1") as f:
        header_line = f.readline().strip()
        header = [h.strip() for h in header_line.split("|")]
        logger.info(f"Columns ({len(header)}): {header[:10]}...")

        for line in f:
            parts = line.strip().split("|")
            row = dict(zip(header, parts))

            acct = row.get("Account_Num", "").strip()
            if not acct:
                continue

            total_read += 1

            address = build_address(row)
            if not address:
                total_skipped += 1
                continue

            appraised = parse_number(row.get("Appraised_Value", "0"))
            market    = parse_number(row.get("Total_Value", "0"))
            bld_area  = parse_number(row.get("Living_Area", "0"))
            yr_built  = row.get("Year_Built", "").strip()
            yr_built  = yr_built if yr_built and yr_built != "0" else None
            # Use TAD_Map as a neighborhood code proxy
            nbhd_code = row.get("TAD_Map", "").strip() or None

            record = {
                "account_number":    acct,
                "address":           address,
                "appraised_value":   appraised,
                "market_value":      market if market > 0 else None,
                "building_area":     int(bld_area) if bld_area > 0 else None,
                "year_built":        yr_built,
                "neighborhood_code": nbhd_code,
                "district":          "TAD",
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
    logger.info("TAD Import complete!")
    logger.info(f"  Total rows read:    {total_read:,}")
    logger.info(f"  Rows imported:      {total_imported:,}")
    logger.info(f"  Rows skipped:       {total_skipped:,}")
    logger.info(f"  Batch errors:       {errors}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import TAD bulk data into Supabase")
    parser.add_argument("--sample", type=int, default=None, help="Only import first N rows (for testing)")
    parser.add_argument("--data-dir", dest="data_dir", default=None, help="Data directory relative to project root (default: TAD_2025)")
    parser.add_argument("--no-overwrite", dest="no_overwrite", action="store_true", help="Skip rows that already exist in Supabase")
    args = parser.parse_args()

    import_tad_data(sample=args.sample, data_dir=args.data_dir, no_overwrite=args.no_overwrite)
