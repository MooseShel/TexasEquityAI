"""
Predictive Tax Savings Estimator
Combines 5 independent signals into a weighted savings prediction
with confidence intervals and protest success probability.

Signals:
1. Equity Floor (KNN-based justified value)
2. Anomaly Z-Score (neighborhood percentile)
3. Condition Delta (subject vs comp condition)
4. Geo Obsolescence (external factors)
5. Flood Zone (FEMA high-risk areas)
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Signal weights for expected value calculation
SIGNAL_WEIGHTS = {
    "equity": 0.40,      # Strongest legal basis (TC 41.43(b)(1))
    "anomaly": 0.20,     # Statistical evidence
    "condition": 0.15,   # Physical depreciation (TC 23.01)
    "geo": 0.10,         # External obsolescence
    "flood": 0.15,       # Environmental/locational
}

# Protest success probability tiers
SUCCESS_TIERS = [
    (4, 0.85, "Very Strong"),    # 4+ signals → 85%
    (3, 0.72, "Strong"),         # 3 signals → 72%
    (2, 0.55, "Moderate"),       # 2 signals → 55%
    (1, 0.35, "Possible"),       # 1 signal → 35%
    (0, 0.10, "Unlikely"),       # 0 signals → 10%
]


class SavingsEstimator:

    def __init__(self, tax_rate: float = 0.025):
        self.tax_rate = tax_rate

    def estimate(self, property_details: Dict, equity_results: Dict) -> Dict:
        """
        Combine all available signals into a savings prediction.
        Returns conservative/expected/best-case estimates with probability.
        """
        appraised = float(property_details.get('appraised_value', 0) or 0)
        if appraised <= 0:
            return {"error": "No appraised value available"}

        signals = []
        signal_values = {}  # signal_name → estimated value

        # ── Signal 1: Equity Floor ────────────────────────────────────────
        equity_floor = float(equity_results.get('justified_value_floor', 0) or 0)
        if equity_floor > 0 and equity_floor < appraised:
            reduction_pct = (appraised - equity_floor) / appraised * 100
            signals.append({
                "signal": "Equity Uniformity (TC 41.43(b)(1))",
                "key": "equity",
                "value": equity_floor,
                "reduction_pct": round(reduction_pct, 1),
                "strength": min(1.0, reduction_pct / 30),  # 30%+ = max strength
            })
            signal_values["equity"] = equity_floor

        # ── Signal 2: Anomaly Z-Score ─────────────────────────────────────
        anomaly = equity_results.get('anomaly_score', {})
        if anomaly and not anomaly.get('error'):
            z = anomaly.get('z_score', 0)
            median_pps = anomaly.get('neighborhood_median_pps', 0)
            area = float(property_details.get('building_area', 0) or 0)
            if z > 1.0 and median_pps > 0 and area > 0:
                anomaly_value = median_pps * area  # Value at neighborhood median
                reduction_pct = (appraised - anomaly_value) / appraised * 100
                signals.append({
                    "signal": "Neighborhood Anomaly (Statistical)",
                    "key": "anomaly",
                    "value": round(anomaly_value),
                    "reduction_pct": round(reduction_pct, 1),
                    "strength": min(1.0, z / 3.0),  # Z=3+ = max strength
                    "detail": f"Z-Score: {z:.1f}, {anomaly.get('percentile', 0):.0f}th percentile",
                })
                signal_values["anomaly"] = anomaly_value

        # ── Signal 3: Condition Delta ─────────────────────────────────────
        cond_delta = equity_results.get('condition_delta', {})
        if cond_delta and cond_delta.get('condition_delta', 0) < -0.5:
            dep_pct = cond_delta.get('depreciation_adjustment_pct', 0)
            if dep_pct > 0:
                condition_value = appraised * (1 - dep_pct / 100)
                signals.append({
                    "signal": "Physical Depreciation (TC 23.01)",
                    "key": "condition",
                    "value": round(condition_value),
                    "reduction_pct": round(dep_pct, 1),
                    "strength": min(1.0, dep_pct / 10),  # 10%+ = max strength
                    "detail": f"Δ={cond_delta['condition_delta']:.1f}",
                })
                signal_values["condition"] = condition_value

        # ── Signal 4: Geo Obsolescence ────────────────────────────────────
        geo_obs = equity_results.get('external_obsolescence', {}) or property_details.get('external_obsolescence', {})
        if geo_obs and geo_obs.get('factors'):
            impact_pct = geo_obs.get('total_impact_pct', 0)
            if impact_pct > 0:
                geo_value = appraised * (1 - impact_pct / 100)
                factor_names = [f['type'] for f in geo_obs['factors']]
                signals.append({
                    "signal": "External Obsolescence (Locational)",
                    "key": "geo",
                    "value": round(geo_value),
                    "reduction_pct": round(impact_pct, 1),
                    "strength": min(1.0, impact_pct / 8),
                    "detail": ", ".join(factor_names),
                })
                signal_values["geo"] = geo_value

        # ── Signal 5: Flood Zone ──────────────────────────────────────────
        flood_zone = property_details.get('flood_zone', '')
        HIGH_RISK_ZONES = {'A', 'AE', 'AH', 'AO', 'AR', 'V', 'VE'}
        if flood_zone and any(flood_zone.upper().startswith(z) for z in HIGH_RISK_ZONES):
            flood_pct = 5.0  # Standard flood zone impact
            flood_value = appraised * (1 - flood_pct / 100)
            signals.append({
                "signal": "Flood Zone Impact (FEMA)",
                "key": "flood",
                "value": round(flood_value),
                "reduction_pct": flood_pct,
                "strength": 0.7,
                "detail": f"Zone {flood_zone}",
            })
            signal_values["flood"] = flood_value

        # ── Combine signals ───────────────────────────────────────────────
        if not signals:
            return {
                "current_appraised": appraised,
                "estimated_value": {"conservative": appraised, "expected": appraised, "best_case": appraised},
                "estimated_savings": {"conservative": 0, "expected": 0, "best_case": 0},
                "protest_success_probability": 0.10,
                "protest_strength": "Unlikely",
                "signals_used": [],
                "signal_breakdown": [],
            }

        # Conservative = equity floor only (if available), else smallest reduction
        conservative_value = signal_values.get("equity", min(s["value"] for s in signals))

        # Best case = most aggressive single signal
        best_case_value = min(s["value"] for s in signals)

        # Expected = weighted average of all signal values
        weighted_sum = 0
        weight_total = 0
        for s in signals:
            w = SIGNAL_WEIGHTS.get(s["key"], 0.1)
            weighted_sum += s["value"] * w
            weight_total += w
        expected_value = weighted_sum / weight_total if weight_total > 0 else conservative_value

        # Ensure ordering: best_case <= expected <= conservative <= appraised
        conservative_value = min(appraised, max(conservative_value, expected_value))
        expected_value = min(conservative_value, max(expected_value, best_case_value))
        best_case_value = min(expected_value, best_case_value)

        # Success probability based on signal count + average strength
        n_signals = len(signals)
        avg_strength = sum(s.get("strength", 0.5) for s in signals) / n_signals
        prob = 0.10
        strength_label = "Unlikely"
        for threshold, base_prob, label in SUCCESS_TIERS:
            if n_signals >= threshold:
                prob = base_prob * (0.7 + 0.3 * avg_strength)  # Scale by signal quality
                strength_label = label
                break

        result = {
            "current_appraised": appraised,
            "estimated_value": {
                "conservative": round(conservative_value),
                "expected": round(expected_value),
                "best_case": round(best_case_value),
            },
            "estimated_savings": {
                "conservative": round((appraised - conservative_value) * self.tax_rate),
                "expected": round((appraised - expected_value) * self.tax_rate),
                "best_case": round((appraised - best_case_value) * self.tax_rate),
            },
            "protest_success_probability": round(min(0.95, prob), 2),
            "protest_strength": strength_label,
            "signals_used": [s["key"] for s in signals],
            "signal_count": n_signals,
            "signal_breakdown": signals,
        }

        logger.info(
            f"SavingsEstimator: {n_signals} signals, "
            f"savings range ${result['estimated_savings']['conservative']:,}–"
            f"${result['estimated_savings']['best_case']:,}, "
            f"probability={result['protest_success_probability']:.0%} ({strength_label})"
        )

        return result
