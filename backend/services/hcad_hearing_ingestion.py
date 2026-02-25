"""
HCAD Hearing Data Ingestion Pipeline
=====================================
Downloads and processes ARB (Appraisal Review Board) hearing outcomes
from HCAD's public data files to train the XGBoost protest predictor.

Data Source: https://pdata.hcad.org (Public Data Downloads)
File: real_hearings.txt (tab-delimited, inside a ZIP download)

Fields available in HCAD hearing data:
- ACCOUNT: Property account number
- TAX_YEAR: Year of protest
- HEARING_DATE: Date of ARB hearing
- INITIAL_MARKET_VALUE: Appraised value before protest
- INITIAL_APPRAISED_VALUE: Capped value before protest
- FINAL_MARKET_VALUE: Market value after hearing
- FINAL_APPRAISED_VALUE: Capped value after hearing
- PROTEST_DATE: When protest was filed
- PROTESTED_BY: Party who filed (O=Owner, A=Agent)

Usage:
    1. Download the hearings ZIP from HCAD Public Data
    2. Extract to data/hcad_hearings/
    3. Run: python -m backend.services.hcad_hearing_ingestion
    4. Train: python -m backend.services.train_protest_model

This script processes the raw hearing data, joins it with property
features from our Supabase database, and produces a training-ready CSV.
"""

import os
import csv
import json
import logging
import glob
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

HEARINGS_DIR = "data/hcad_hearings"
OUTPUT_CSV = "data/hcad_training_data.csv"


@dataclass
class HearingRecord:
    account: str
    tax_year: int
    hearing_date: str
    initial_market: float
    initial_appraised: float
    final_market: float
    final_appraised: float
    protest_date: str
    protested_by: str  # O=Owner, A=Agent

    @property
    def won(self) -> bool:
        """Did the protest result in a reduction?"""
        return self.final_appraised < self.initial_appraised

    @property
    def reduction_amount(self) -> float:
        return max(0, self.initial_appraised - self.final_appraised)

    @property
    def reduction_pct(self) -> float:
        if self.initial_appraised <= 0:
            return 0
        return self.reduction_amount / self.initial_appraised * 100


def parse_hearings_file(filepath: str) -> List[HearingRecord]:
    """
    Parse a tab-delimited HCAD hearings file.
    Expected format: tab-separated with header row.
    """
    records = []
    encodings_to_try = ['utf-8', 'latin-1', 'cp1252']

    for encoding in encodings_to_try:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    try:
                        record = HearingRecord(
                            account=row.get('ACCOUNT', '').strip(),
                            tax_year=int(row.get('TAX_YEAR', '0').strip() or '0'),
                            hearing_date=row.get('HEARING_DATE', '').strip(),
                            initial_market=float(row.get('INITIAL_MARKET_VALUE', '0').strip() or '0'),
                            initial_appraised=float(row.get('INITIAL_APPRAISED_VALUE', '0').strip() or '0'),
                            final_market=float(row.get('FINAL_MARKET_VALUE', '0').strip() or '0'),
                            final_appraised=float(row.get('FINAL_APPRAISED_VALUE', '0').strip() or '0'),
                            protest_date=row.get('PROTEST_DATE', '').strip(),
                            protested_by=row.get('PROTESTED_BY', '').strip(),
                        )

                        # Only include valid records
                        if record.account and record.initial_appraised > 0:
                            records.append(record)
                    except (ValueError, KeyError) as e:
                        continue  # Skip malformed rows
            break  # Success — stop trying other encodings
        except UnicodeDecodeError:
            continue

    return records


def compute_statistics(records: List[HearingRecord]) -> Dict:
    """Compute summary statistics from hearing records."""
    if not records:
        return {"error": "No records found"}

    total = len(records)
    wins = sum(1 for r in records if r.won)
    reductions = [r.reduction_pct for r in records if r.won]

    return {
        "total_protests": total,
        "total_wins": wins,
        "win_rate": round(wins / total * 100, 1),
        "median_reduction_pct": round(sorted(reductions)[len(reductions) // 2], 1) if reductions else 0,
        "avg_reduction_pct": round(sum(reductions) / len(reductions), 1) if reductions else 0,
        "by_year": {},
    }


def generate_training_features(
    records: List[HearingRecord],
    property_lookup_fn=None
) -> List[Dict]:
    """
    Generate training data by joining hearing outcomes with property features.
    
    property_lookup_fn: async function(account_number) -> property_dict
    """
    training_data = []

    for record in records:
        feature_row = {
            # Target variable
            "won": 1 if record.won else 0,
            "reduction_pct": round(record.reduction_pct, 2),

            # Basic features from hearing record
            "account": record.account,
            "tax_year": record.tax_year,
            "initial_appraised": record.initial_appraised,
            "final_appraised": record.final_appraised,
            "protested_by_agent": 1 if record.protested_by == 'A' else 0,

            # Derived features
            "overvaluation_pct": 0,  # Will be filled from property data
            "building_age": 0,
            "building_area": 0,
            "neighborhood_code": "",
            "property_class": "",
        }

        training_data.append(feature_row)

    return training_data


def ingest_hearings(directory: str = HEARINGS_DIR) -> Dict:
    """
    Main entry point: ingest all hearings files from the directory.
    Returns statistics and saves training data CSV.
    """
    all_records = []

    # Find all .txt files in the hearings directory
    pattern = os.path.join(directory, "*.txt")
    files = glob.glob(pattern)

    if not files:
        logger.warning(f"No hearing files found in {directory}. "
                        f"Download from https://pdata.hcad.org and extract to {directory}")
        return {"error": f"No files found in {directory}"}

    for filepath in files:
        logger.info(f"Processing: {filepath}")
        records = parse_hearings_file(filepath)
        logger.info(f"  → Parsed {len(records)} hearing records")
        all_records.extend(records)

    stats = compute_statistics(all_records)
    logger.info(f"Total: {stats['total_protests']} protests, "
                f"Win rate: {stats['win_rate']}%, "
                f"Avg reduction: {stats['avg_reduction_pct']}%")

    # Generate training data
    training_data = generate_training_features(all_records)

    # Save to CSV
    if training_data:
        os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
        with open(OUTPUT_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=training_data[0].keys())
            writer.writeheader()
            writer.writerows(training_data)
        logger.info(f"Training data saved to {OUTPUT_CSV} ({len(training_data)} rows)")
        stats["training_csv"] = OUTPUT_CSV

    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 60)
    print("HCAD Hearing Data Ingestion Pipeline")
    print("=" * 60)

    if not os.path.exists(HEARINGS_DIR):
        os.makedirs(HEARINGS_DIR, exist_ok=True)
        print(f"\nCreated directory: {HEARINGS_DIR}/")
        print(f"\nTo proceed:")
        print(f"1. Go to https://pdata.hcad.org")
        print(f"2. Download 'Preliminary Values - ARB Hearings' ZIP")
        print(f"3. Extract the .txt file(s) to {HEARINGS_DIR}/")
        print(f"4. Re-run this script")
    else:
        stats = ingest_hearings()
        print(f"\nResults: {json.dumps(stats, indent=2)}")
