#!/usr/bin/env python3
"""
Multi-County State Class Updater
Updates state_class for CCAD, TAD, and DCAD records already in Supabase.

Usage:
    python scripts/update_state_class_multicounty.py
"""

import os, sys, csv, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 500
DATA_DIR = r"C:\Users\Husse\Downloads\Data"

# DCAD DIVISION_CD → SPTD state class mapping
DCAD_DIV_MAP = {
    "RES": "A1",
    "COM": "F1",
    "BPP": "L1",
}


def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)
    return create_client(url, key)


def update_ccad(sb):
    """CCAD: CSV with propID (account_number) and propCategoryCode (SPTD state class)."""
    filepath = os.path.join(DATA_DIR, "CCAD", "CCAD_2025_data.csv")
    if not os.path.exists(filepath):
        logger.warning(f"CCAD file not found: {filepath}")
        return

    logger.info(f"Processing CCAD: {filepath}")
    batch = []
    total = 0

    with open(filepath, "r", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            acct = (row.get("propID") or "").strip().strip('"')
            sc = (row.get("propCategoryCode") or "").strip().strip('"')
            if not acct or not sc:
                continue

            batch.append({"account_number": acct, "state_class": sc})
            total += 1

            if len(batch) >= BATCH_SIZE:
                try:
                    sb.table("properties").upsert(
                        batch, on_conflict="account_number"
                    ).execute()
                except Exception as e:
                    logger.warning(f"CCAD batch error: {e}")
                batch = []
                if total % 10000 == 0:
                    logger.info(f"  CCAD: {total:,} processed")

    if batch:
        try:
            sb.table("properties").upsert(batch, on_conflict="account_number").execute()
        except Exception as e:
            logger.warning(f"CCAD final batch error: {e}")

    logger.info(f"CCAD complete: {total:,} records processed")


def update_tad(sb):
    """TAD: Pipe-delimited with Account_Num [2] and Property_Class [13]."""
    filepath = os.path.join(DATA_DIR, "TAD", "PropertyData_2026.txt")
    if not os.path.exists(filepath):
        logger.warning(f"TAD file not found: {filepath}")
        return

    logger.info(f"Processing TAD: {filepath}")
    batch = []
    total = 0

    with open(filepath, "r", encoding="latin-1") as f:
        header = f.readline()  # skip header
        for line in f:
            cols = line.strip().split("|")
            if len(cols) < 14:
                continue

            acct = cols[2].strip()
            sc = cols[13].strip()
            if not acct or not sc:
                continue

            batch.append({"account_number": acct, "state_class": sc})
            total += 1

            if len(batch) >= BATCH_SIZE:
                try:
                    sb.table("properties").upsert(
                        batch, on_conflict="account_number"
                    ).execute()
                except Exception as e:
                    logger.warning(f"TAD batch error: {e}")
                batch = []
                if total % 10000 == 0:
                    logger.info(f"  TAD: {total:,} processed")

    if batch:
        try:
            sb.table("properties").upsert(batch, on_conflict="account_number").execute()
        except Exception as e:
            logger.warning(f"TAD final batch error: {e}")

    logger.info(f"TAD complete: {total:,} records processed")


def update_dcad(sb):
    """DCAD: CSV with ACCOUNT_NUM and DIVISION_CD (RES/COM/BPP)."""
    filepath = os.path.join(DATA_DIR, "DCAD", "ACCOUNT_INFO.CSV")
    if not os.path.exists(filepath):
        logger.warning(f"DCAD file not found: {filepath}")
        return

    logger.info(f"Processing DCAD: {filepath}")
    batch = []
    total = 0

    with open(filepath, "r", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            acct = (row.get("ACCOUNT_NUM") or "").strip().strip('"')
            div = (row.get("DIVISION_CD") or "").strip().strip('"').upper()
            if not acct:
                continue

            sc = DCAD_DIV_MAP.get(div)
            if not sc:
                continue

            batch.append({"account_number": acct, "state_class": sc})
            total += 1

            if len(batch) >= BATCH_SIZE:
                try:
                    sb.table("properties").upsert(
                        batch, on_conflict="account_number"
                    ).execute()
                except Exception as e:
                    logger.warning(f"DCAD batch error: {e}")
                batch = []
                if total % 10000 == 0:
                    logger.info(f"  DCAD: {total:,} processed")

    if batch:
        try:
            sb.table("properties").upsert(batch, on_conflict="account_number").execute()
        except Exception as e:
            logger.warning(f"DCAD final batch error: {e}")

    logger.info(f"DCAD complete: {total:,} records processed")


if __name__ == "__main__":
    sb = get_supabase()
    logger.info("=" * 55)
    logger.info("  MULTI-COUNTY STATE_CLASS UPDATE")
    logger.info("=" * 55)

    update_ccad(sb)
    update_tad(sb)
    update_dcad(sb)

    logger.info("=" * 55)
    logger.info("All counties processed!")
    logger.info("=" * 55)
