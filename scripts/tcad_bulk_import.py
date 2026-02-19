#!/usr/bin/env python3
"""
TCAD Bulk Data Import Script
Imports TCAD (Travis Central Appraisal District) 2025 property data into Supabase.

Data source: traviscad.org/public-information → "2025 Certified Export"
Format: ProdigyCad Legacy 8.0.30 fixed-width text files

Key files:
  PROP.TXT     — master property record (9247 chars/record, one per line)
  IMP_DET.TXT  — improvement detail: yr_built + building area per prop_id

PROP.TXT field offsets (1-indexed, from Layout Excel):
  prop_id            1-12    Property ID (account number)
  situs_street_prefx 1040-1049  Street prefix
  situs_street       1050-1099  Street name
  situs_street_suffix 1100-1109 Street suffix
  situs_city         1110-1139  City
  situs_zip          1140-1149  ZIP code
  hood_cd            1686-1695  Neighborhood code
  appraised_val      1916-1930  Appraised value
  market_value       4214-4227  Market value
  situs_num          4460-4474  Street number

IMP_DET.TXT field offsets:
  prop_id            1-12
  yr_built           86-89
  imprv_det_area     94-108   (living area sq ft)

Usage:
    python scripts/tcad_bulk_import.py                          # Full import
    python scripts/tcad_bulk_import.py --sample 5000            # First N rows (test)
    python scripts/tcad_bulk_import.py --data-dir TCAD_DATA2    # Different directory
    python scripts/tcad_bulk_import.py --no-overwrite           # Skip existing rows
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
DEFAULT_DATA_DIR = "TCAD_DATA"

# PROP.TXT fixed-width slices (0-indexed: start-1, end)
PROP_FIELDS = {
    "prop_id":             (0,   12),
    "situs_num":           (4459, 4474),
    "situs_street_prefx":  (1039, 1049),
    "situs_street":        (1049, 1099),
    "situs_street_suffix": (1099, 1109),
    "situs_city":          (1109, 1139),
    "situs_zip":           (1139, 1149),
    "hood_cd":             (1685, 1695),
    "appraised_val":       (1915, 1930),
    "market_value":        (4213, 4227),
}

# IMP_DET.TXT fixed-width slices
IMP_FIELDS = {
    "prop_id":         (0,  12),
    "yr_built":        (85, 89),
    "imprv_det_area":  (93, 108),
}


def extract(line: str, field_slice: tuple) -> str:
    """Extract a fixed-width field from a line and strip whitespace."""
    s, e = field_slice
    return line[s:e].strip() if len(line) >= e else ""


def parse_number(val: str, default=0):
    try:
        return float(val.strip()) if val.strip() else default
    except ValueError:
        return default


def load_imp_det(filepath: str, sample_limit: int = None) -> dict:
    """
    Load IMP_DET.TXT into a dict: prop_id → {yr_built, building_area (max area seen)}
    Takes the maximum imprv_det_area per prop_id (main structure).
    """
    result = {}
    with open(filepath, encoding="latin-1") as f:
        for line in f:
            if len(line) < 108:
                continue
            pid = extract(line, IMP_FIELDS["prop_id"])
            if not pid:
                continue
            yr   = extract(line, IMP_FIELDS["yr_built"])
            area = parse_number(extract(line, IMP_FIELDS["imprv_det_area"]))

            if pid not in result:
                result[pid] = {"yr_built": yr, "building_area": area}
            else:
                # Keep largest area (main building)
                if area > result[pid]["building_area"]:
                    result[pid]["building_area"] = area
                # Use earliest year built
                if yr and (not result[pid]["yr_built"] or yr < result[pid]["yr_built"]):
                    result[pid]["yr_built"] = yr

    logger.info(f"Loaded {len(result):,} improvement records from IMP_DET.TXT")
    return result


def import_tcad_data(sample: int = None, data_dir: str = None, no_overwrite: bool = False):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    client = create_client(url, key)
    logger.info(f"Connected to Supabase: {url}")

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resolved_dir = os.path.join(project_root, data_dir or DEFAULT_DATA_DIR)

    prop_file   = os.path.join(resolved_dir, "PROP.TXT")
    imp_file    = os.path.join(resolved_dir, "IMP_DET.TXT")

    for f in [prop_file, imp_file]:
        if not os.path.exists(f):
            logger.error(f"Required file not found: {f}")
            sys.exit(1)

    logger.info(f"Data directory: {resolved_dir}")
    logger.info(f"Mode: {'SKIP existing (no-overwrite)' if no_overwrite else 'OVERWRITE existing'}")

    # Load improvement detail into memory (~100k records, manageable)
    logger.info("Loading IMP_DET.TXT (building area / year built)...")
    imp_data = load_imp_det(imp_file)

    logger.info("Streaming PROP.TXT and building records...")
    batch = []
    total_read = total_imported = total_skipped = errors = 0

    with open(prop_file, encoding="latin-1") as f:
        for line in f:
            if len(line) < 200:
                continue

            pid = extract(line, PROP_FIELDS["prop_id"])
            if not pid:
                continue

            total_read += 1

            # Build address
            situs_num    = extract(line, PROP_FIELDS["situs_num"])
            st_prefix    = extract(line, PROP_FIELDS["situs_street_prefx"])
            st_name      = extract(line, PROP_FIELDS["situs_street"])
            st_suffix    = extract(line, PROP_FIELDS["situs_street_suffix"])
            city         = extract(line, PROP_FIELDS["situs_city"])
            zipcode      = extract(line, PROP_FIELDS["situs_zip"])[:5]

            street = " ".join(p for p in [situs_num, st_prefix, st_name, st_suffix] if p)
            if not street or street.startswith("0 ") or street == "0":
                total_skipped += 1
                continue

            address = ", ".join(p for p in [street, city, "TX", zipcode] if p)

            nbhd_code  = extract(line, PROP_FIELDS["hood_cd"]) or None
            appraised  = parse_number(extract(line, PROP_FIELDS["appraised_val"]))
            market     = parse_number(extract(line, PROP_FIELDS["market_value"]))

            # Join improvement data
            imp = imp_data.get(pid, {})
            bld_area = imp.get("building_area", 0)
            yr_built = imp.get("yr_built") or None
            yr_built = yr_built if yr_built and yr_built != "0000" else None

            record = {
                "account_number":    pid,
                "address":           address,
                "appraised_value":   appraised,
                "market_value":      market if market > 0 else None,
                "building_area":     int(bld_area) if bld_area > 0 else None,
                "year_built":        yr_built,
                "neighborhood_code": nbhd_code,
                "district":          "TCAD",
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
                    logger.info(f"  Upserted batch | imported: {total_imported:,} | read: {total_read:,}")
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
    logger.info("TCAD Import complete!")
    logger.info(f"  Total rows read:    {total_read:,}")
    logger.info(f"  Rows imported:      {total_imported:,}")
    logger.info(f"  Rows skipped:       {total_skipped:,}  (zero/blank address)")
    logger.info(f"  Batch errors:       {errors}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import TCAD bulk data into Supabase")
    parser.add_argument("--sample", type=int, default=None, help="Only import first N rows (for testing)")
    parser.add_argument("--data-dir", dest="data_dir", default=None, help="Data directory relative to project root (default: TCAD_DATA)")
    parser.add_argument("--no-overwrite", dest="no_overwrite", action="store_true", help="Skip rows that already exist in Supabase")
    args = parser.parse_args()

    import_tcad_data(sample=args.sample, data_dir=args.data_dir, no_overwrite=args.no_overwrite)
