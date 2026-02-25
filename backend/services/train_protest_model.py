"""
XGBoost Protest Outcome Model Trainer
======================================
Trains on 544K+ HCAD ARB hearing records to predict protest outcomes.

Features extracted from hearing data:
- State class code (residential type: A1, B1, etc.)
- Initial overvaluation signal (initial_market vs initial_appraised)
- Hearing type (F=Formal, I=Informal)
- Agent vs Owner protest
- Tax year (temporal trends)
- Value magnitude bucket

Target: Binary classification (won = final_appraised < initial_appraised)
"""

import os
import csv
import json
import logging
import pickle
import numpy as np
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

HEARINGS_FILE = r"C:\Users\Husse\Downloads\Data\HCAD\Hearing_files\arb_hearings_real.txt"
PROTEST_FILE = r"C:\Users\Husse\Downloads\Data\HCAD\Hearing_files\arb_protest_real.txt"
MODEL_OUTPUT = "models/protest_predictor.json"
STATS_OUTPUT = "models/hearing_stats.json"


def load_protest_data() -> Dict[str, str]:
    """Load protest data to get protested_by (Agent/Owner) info."""
    protest_map = {}
    try:
        with open(PROTEST_FILE, 'r', encoding='latin-1') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                acct = row.get('acct', '').strip()
                by = row.get('protested_by', '').strip()
                if acct and by:
                    protest_map[acct] = by
    except Exception as e:
        logger.warning(f"Could not load protest data: {e}")
    return protest_map


def load_hearing_records() -> List[Dict]:
    """Load and parse all hearing records with feature engineering."""
    protest_map = load_protest_data()
    records = []

    with open(HEARINGS_FILE, 'r', encoding='latin-1') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            try:
                acct = row.get('acct', '').strip()
                init_appraised = float(row.get('Initial_Appraised_Value', '0').strip() or '0')
                final_appraised = float(row.get('Final_Appraised_Value', '0').strip() or '0')
                init_market = float(row.get('Initial_Market_Value', '0').strip() or '0')
                final_market = float(row.get('Final_Market_Value', '0').strip() or '0')

                if init_appraised <= 0 or not acct:
                    continue

                state_class = row.get('State_Class_Code', '').strip()
                hearing_type = row.get('Hearing_Type', '').strip()
                tax_year = int(row.get('Tax_Year', '0').strip() or '0')
                agent_code = row.get('Agent_Code', '').strip()

                # Target
                won = 1 if final_appraised < init_appraised else 0
                reduction_pct = max(0, (init_appraised - final_appraised) / init_appraised * 100)

                # Feature: market vs appraised gap (cap impact indicator)
                market_appraised_gap = 0
                if init_market > 0:
                    market_appraised_gap = (init_market - init_appraised) / init_market * 100

                # Feature: protested by agent or owner
                protested_by = protest_map.get(acct, '')
                is_agent = 1 if (protested_by == 'Agent' or (agent_code and agent_code != '0')) else 0

                # Feature: value magnitude bucket (log scale)
                value_bucket = 0
                if init_appraised > 0:
                    value_bucket = min(10, int(np.log10(init_appraised)))

                # Feature: state class encoding
                # A1=Single Family, B1=Multifamily, F1=Commercial, etc.
                class_map = {
                    'A1': 1, 'A2': 1, 'A3': 1, 'A4': 1,  # Residential
                    'B1': 2, 'B2': 2, 'B3': 2, 'B4': 2,  # Multifamily
                    'C1': 3, 'C2': 3,                      # Vacant land
                    'D1': 4, 'D2': 4,                      # Ag/Rural
                    'E1': 5, 'E2': 5, 'E3': 5, 'E4': 5,  # Farm/Ranch
                    'F1': 6, 'F2': 6,                      # Commercial
                    'G1': 7,                                # Oil/Gas
                    'J1': 8, 'J2': 8, 'J3': 8,            # Utilities
                    'L1': 9, 'L2': 9,                      # Personal Property
                    'M1': 10,                               # Mobile Home
                    'O1': 11, 'O2': 11,                    # Other
                    'XB': 12, 'XC': 12, 'XD': 12,         # Exempt
                    'XV': 12, 'XR': 12, 'XS': 12,         # Exempt
                }
                numeric_class = class_map.get(state_class[:2] if state_class else '', 0)

                # Feature: hearing type
                # F=Formal, I=Informal
                is_formal = 1 if hearing_type == 'F' else 0

                records.append({
                    'won': won,
                    'reduction_pct': round(reduction_pct, 2),
                    'initial_appraised': init_appraised,
                    'market_appraised_gap': round(market_appraised_gap, 2),
                    'is_agent': is_agent,
                    'value_bucket': value_bucket,
                    'numeric_class': numeric_class,
                    'is_formal': is_formal,
                    'tax_year': tax_year,
                    'state_class': state_class,
                    'account': acct,
                })

            except (ValueError, KeyError):
                continue

    return records


def train_model(records: List[Dict]) -> Dict:
    """Train XGBoost model on hearing records."""
    try:
        import xgboost as xgb
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
    except ImportError:
        print("Required: pip install xgboost scikit-learn")
        print("Installing now...")
        os.system("pip install xgboost scikit-learn")
        import xgboost as xgb
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, roc_auc_score, classification_report

    # Feature matrix
    feature_cols = [
        'market_appraised_gap',
        'is_agent',
        'value_bucket',
        'numeric_class',
        'is_formal',
        'tax_year',
    ]

    X = np.array([[r[c] for c in feature_cols] for r in records])
    y = np.array([r['won'] for r in records])

    print(f"\nDataset: {len(X):,} records, {sum(y):,} wins ({sum(y)/len(y)*100:.1f}%)")
    print(f"Features: {feature_cols}")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"Train: {len(X_train):,}  |  Test: {len(X_test):,}")

    # Train XGBoost
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        eval_metric='logloss',
        random_state=42,
        use_label_encoder=False,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # Evaluate
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_proba)

    print(f"\n{'='*50}")
    print(f"Model Performance:")
    print(f"  Accuracy: {accuracy:.3f}")
    print(f"  AUC-ROC:  {auc:.3f}")
    print(f"{'='*50}")
    print(classification_report(y_test, y_pred, target_names=['Lost', 'Won']))

    # Feature importance
    importances = model.feature_importances_
    print("\nFeature Importance:")
    for feat, imp in sorted(zip(feature_cols, importances), key=lambda x: -x[1]):
        print(f"  {feat:30s} {imp:.3f}")

    # Save model
    os.makedirs("models", exist_ok=True)
    model.save_model(MODEL_OUTPUT)
    print(f"\n✅ Model saved to {MODEL_OUTPUT}")

    # Compute and save neighborhood win rate statistics
    # These are used as lookup features in the live predictor
    nbhd_stats = defaultdict(lambda: {'wins': 0, 'total': 0})
    class_stats = defaultdict(lambda: {'wins': 0, 'total': 0})

    for r in records:
        sc = r.get('state_class', '')[:2]
        class_stats[sc]['total'] += 1
        class_stats[sc]['wins'] += r['won']

    stats = {
        "model_version": "xgboost_v1",
        "training_records": len(records),
        "overall_win_rate": round(sum(y) / len(y) * 100, 1),
        "test_accuracy": round(accuracy, 3),
        "test_auc_roc": round(auc, 3),
        "feature_importance": {
            feat: round(float(imp), 3)
            for feat, imp in zip(feature_cols, importances)
        },
        "class_win_rates": {
            sc: round(d['wins'] / d['total'] * 100, 1)
            for sc, d in sorted(class_stats.items())
            if d['total'] > 100
        },
    }

    with open(STATS_OUTPUT, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"✅ Statistics saved to {STATS_OUTPUT}")

    return stats


def main():
    print("=" * 60)
    print("HCAD XGBoost Protest Predictor Training")
    print("=" * 60)

    print("\n📥 Loading hearing records...")
    records = load_hearing_records()
    print(f"   Loaded {len(records):,} records")

    if len(records) < 100:
        print("❌ Not enough records to train. Check data files.")
        return

    print("\n🏋️ Training XGBoost model...")
    stats = train_model(records)

    print(f"\n🎉 Done! Model ready at {MODEL_OUTPUT}")
    print(f"   Overall HCAD win rate: {stats['overall_win_rate']}%")
    print(f"   Model AUC: {stats['test_auc_roc']}")


if __name__ == "__main__":
    main()
