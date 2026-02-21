#!/usr/bin/env python3
"""
HCAD Deed Data Import Script
Imports deed transfer records from HCAD deeds.txt into Supabase property_deeds table,
then backfills last_sale_date and deed_count on the properties table.

Usage:
    python scripts/hcad_deed_import.py                       # Import all deeds
    python scripts/hcad_deed_import.py --sample 1000         # Import first 1000 rows
    python scripts/hcad_deed_import.py --data-dir hcad_data_2024  # Alt data directory
    python scripts/hcad_deed_import.py --backfill-only       # Only update properties table

Data source: hcad_2025_data/deeds.txt
Columns: acct, dos, clerk_yr, clerk_id, deed_id
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def parse_date(val: str):
    """Parse MM/DD/YYYY date string to ISO format (YYYY-MM-DD)."""
    if not val or not val.strip():
        return None
    val = val.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_int(val: str, default=None):
    try:
        return int(val.strip()) if val and val.strip() else default
    except (ValueError, AttributeError):
        return default


def import_deeds(sample: int = None, data_dir: str = None):
    """Import deed records from deeds.txt into property_deeds table."""
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
    deeds_file = os.path.join(resolved_dir, "deeds.txt")

    if not os.path.exists(deeds_file):
        logger.error(f"Deeds file not found: {deeds_file}")
        sys.exit(1)

    logger.info(f"Reading {deeds_file} ...")
    if sample:
        logger.info(f"Sample mode: first {sample} rows")

    batch = []
    total_read = 0
    total_imported = 0
    total_skipped = 0
    errors = 0

    with open(deeds_file, "r", encoding="latin-1") as f:
        header = f.readline().strip().split("\t")
        logger.info(f"Columns ({len(header)}): {header}")

        for line in f:
            row = dict(zip(header, line.strip().split("\t")))
            total_read += 1

            acct = row.get("acct", "").strip()
            dos = row.get("dos", "").strip()
            clerk_yr = row.get("clerk_yr", "").strip()
            clerk_id = row.get("clerk_id", "").strip()
            deed_id_raw = row.get("deed_id", "").strip()

            if not acct:
                total_skipped += 1
                continue

            date_of_sale = parse_date(dos)
            deed_id = parse_int(deed_id_raw, default=1)

            record = {
                "acct": acct,
                "date_of_sale": date_of_sale,
                "clerk_year": parse_int(clerk_yr),
                "clerk_id": clerk_id if clerk_id else None,
                "deed_id": deed_id,
            }
            # Remove None values
            record = {k: v for k, v in record.items() if v is not None}
            batch.append(record)
            total_imported += 1

            # Flush batch
            if len(batch) >= BATCH_SIZE:
                try:
                    client.table("property_deeds").upsert(
                        batch, on_conflict="acct,deed_id"
                    ).execute()
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
            client.table("property_deeds").upsert(
                batch, on_conflict="acct,deed_id"
            ).execute()
            logger.info(f"  Upserted final batch of {len(batch)} rows.")
        except Exception as e:
            logger.error(f"  Final batch upsert failed: {e}")
            errors += 1

    logger.info("=" * 60)
    logger.info(f"Deed Import Complete!")
    logger.info(f"  Total rows read:     {total_read:,}")
    logger.info(f"  Rows imported:       {total_imported:,}")
    logger.info(f"  Rows skipped:        {total_skipped:,}")
    logger.info(f"  Batch errors:        {errors}")
    logger.info("=" * 60)

    return client


def backfill_properties(client):
    """
    Update properties.last_sale_date and properties.deed_count
    by querying the most recent deed per account from property_deeds.
    
    Uses pagination to process all deeds in chunks.
    """
    logger.info("=" * 60)
    logger.info("Backfilling properties.last_sale_date and deed_count...")

    # Fetch all distinct accounts with deeds, ordered by acct
    offset = 0
    page_size = 1000
    total_updated = 0
    errors = 0

    while True:
        try:
            # Get a page of deeds grouped by account — most recent first
            result = client.table("property_deeds") \
                .select("acct, date_of_sale") \
                .order("acct") \
                .order("date_of_sale", desc=True) \
                .range(offset, offset + page_size - 1) \
                .execute()

            rows = result.data if result.data else []
            if not rows:
                break

            # Group by account — compute last_sale_date and deed_count
            acct_data = {}
            for row in rows:
                acct = row["acct"]
                dos = row.get("date_of_sale")
                if acct not in acct_data:
                    acct_data[acct] = {"last_sale_date": dos, "count": 1}
                else:
                    acct_data[acct]["count"] += 1
                    # Keep the most recent date
                    if dos and (not acct_data[acct]["last_sale_date"] or dos > acct_data[acct]["last_sale_date"]):
                        acct_data[acct]["last_sale_date"] = dos

            # Batch update properties table
            for acct, data in acct_data.items():
                try:
                    update = {"deed_count": data["count"]}
                    if data["last_sale_date"]:
                        update["last_sale_date"] = data["last_sale_date"]
                    client.table("properties").update(update).eq("account_number", acct).execute()
                    total_updated += 1
                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        logger.warning(f"  Failed to update {acct}: {e}")

            logger.info(f"  Backfill progress: {total_updated:,} accounts updated (page offset {offset:,})")
            offset += page_size

            # If we got fewer rows than page_size, we're done
            if len(rows) < page_size:
                break

        except Exception as e:
            logger.error(f"  Backfill page query failed at offset {offset}: {e}")
            errors += 1
            break

    logger.info("=" * 60)
    logger.info(f"Backfill Complete!")
    logger.info(f"  Properties updated:  {total_updated:,}")
    logger.info(f"  Errors:              {errors}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import HCAD deed data into Supabase")
    parser.add_argument("--sample", type=int, default=None, help="Only import first N rows (for testing)")
    parser.add_argument("--data-dir", dest="data_dir", default=None,
                        help="Data directory name relative to project root (default: hcad_2025_data)")
    parser.add_argument("--backfill-only", dest="backfill_only", action="store_true",
                        help="Skip deed import, only backfill properties.last_sale_date")
    parser.add_argument("--skip-backfill", dest="skip_backfill", action="store_true",
                        help="Import deeds but skip the properties backfill step")
    args = parser.parse_args()

    if args.backfill_only:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            logger.error("SUPABASE_URL and SUPABASE_KEY must be set in .env")
            sys.exit(1)
        sb_client = create_client(url, key)
        backfill_properties(sb_client)
    else:
        sb_client = import_deeds(sample=args.sample, data_dir=args.data_dir)
        if not args.skip_backfill:
            backfill_properties(sb_client)
