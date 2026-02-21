"""
Neighborhood Anomaly Detector
Identifies statistically over-assessed properties within a neighborhood
using Z-score analysis on $/sqft (price per square foot).

A property with Z > 1.5 is assessed significantly above its neighbors,
providing a strong §41.43(b)(1) equity uniformity argument.
"""

import logging
import numpy as np
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AnomalyDetectorAgent:

    Z_THRESHOLD = 1.5  # Flag properties above this Z-score (~93rd percentile)
    MIN_NEIGHBORHOOD_SIZE = 5  # Need at least this many properties for meaningful stats

    def __init__(self):
        from backend.db.supabase_client import supabase_service
        self.db = supabase_service

    async def scan_neighborhood(self, neighborhood_code: str, district: str = "HCAD",
                                 limit: int = 500) -> Dict:
        """
        Scan all properties in a neighborhood and return anomaly analysis.
        Returns stats + list of flagged over-assessed properties.
        """
        if not neighborhood_code:
            return {"error": "No neighborhood code provided", "flagged": []}

        # Fetch all properties in the neighborhood
        props = await self._get_neighborhood_properties(neighborhood_code, district, limit)

        if len(props) < self.MIN_NEIGHBORHOOD_SIZE:
            return {
                "error": f"Insufficient data: only {len(props)} properties in neighborhood {neighborhood_code} (need {self.MIN_NEIGHBORHOOD_SIZE}+)",
                "flagged": [],
                "neighborhood_code": neighborhood_code,
                "property_count": len(props),
            }

        # Compute PPS for each property
        scored = []
        for p in props:
            area = p.get("building_area", 0) or 0
            val = p.get("appraised_value", 0) or 0
            if area > 0 and val > 0:
                scored.append({
                    "account_number": p.get("account_number", ""),
                    "address": p.get("address", ""),
                    "appraised_value": val,
                    "building_area": area,
                    "year_built": p.get("year_built"),
                    "pps": round(val / area, 2),
                })

        if len(scored) < self.MIN_NEIGHBORHOOD_SIZE:
            return {
                "error": f"Only {len(scored)} valid properties after filtering zero-area/value",
                "flagged": [],
                "neighborhood_code": neighborhood_code,
                "property_count": len(scored),
            }

        # Compute neighborhood statistics
        pps_values = np.array([s["pps"] for s in scored])
        mean_pps = float(np.mean(pps_values))
        std_pps = float(np.std(pps_values))
        median_pps = float(np.median(pps_values))
        q1 = float(np.percentile(pps_values, 25))
        q3 = float(np.percentile(pps_values, 75))

        stats = {
            "neighborhood_code": neighborhood_code,
            "district": district,
            "property_count": len(scored),
            "mean_pps": round(mean_pps, 2),
            "std_pps": round(std_pps, 2),
            "median_pps": round(median_pps, 2),
            "q1_pps": round(q1, 2),
            "q3_pps": round(q3, 2),
        }

        # Score each property
        flagged = []
        if std_pps > 0:
            for s in scored:
                z = (s["pps"] - mean_pps) / std_pps
                percentile = float(np.sum(pps_values <= s["pps"]) / len(pps_values) * 100)
                over_assessment = round((s["pps"] - median_pps) * s["building_area"])

                s["z_score"] = round(z, 2)
                s["percentile"] = round(percentile, 1)
                s["estimated_over_assessment"] = max(0, over_assessment)
                s["neighborhood_median_pps"] = round(median_pps, 2)

                if z > self.Z_THRESHOLD:
                    s["flag"] = "🔴 OVER-ASSESSED"
                    flagged.append(s)
                elif z > 1.0:
                    s["flag"] = "🟡 ELEVATED"

            # Sort flagged by Z-score descending (worst offenders first)
            flagged.sort(key=lambda x: x["z_score"], reverse=True)

        logger.info(
            f"AnomalyDetector: Neighborhood {neighborhood_code} — "
            f"{len(scored)} properties, {len(flagged)} flagged, "
            f"median PPS=${median_pps:.2f}, std=${std_pps:.2f}"
        )

        return {
            "stats": stats,
            "flagged": flagged,
            "flagged_count": len(flagged),
            "all_scored": scored,
        }

    async def score_property(self, account_number: str, neighborhood_code: str = None,
                              district: str = "HCAD") -> Optional[Dict]:
        """
        Score a single property against its neighborhood.
        If neighborhood_code is not provided, looks it up from the DB.
        """
        if not account_number:
            return None

        # Look up property details if needed
        if not neighborhood_code:
            prop = await self.db.get_property_by_account(account_number)
            if not prop:
                logger.warning(f"AnomalyDetector: Property {account_number} not found in DB")
                return None
            neighborhood_code = prop.get("neighborhood_code")
            district = prop.get("district", district)

        if not neighborhood_code:
            return None

        # Scan the whole neighborhood
        result = await self.scan_neighborhood(neighborhood_code, district)
        if result.get("error"):
            return {"account_number": account_number, "error": result["error"]}

        # Find our property in the scored list
        all_scored = result.get("all_scored", [])
        for s in all_scored:
            if s["account_number"] == account_number:
                s["neighborhood_stats"] = result.get("stats", {})
                return s

        return {"account_number": account_number, "error": "Property not found in neighborhood scan"}

    async def _get_neighborhood_properties(self, neighborhood_code: str, district: str,
                                            limit: int = 500) -> List[Dict]:
        """Fetch all properties in a neighborhood from Supabase."""
        if not self.db.client:
            return []
        try:
            response = (
                self.db.client.table("properties")
                .select("account_number,address,appraised_value,building_area,year_built,neighborhood_code")
                .eq("neighborhood_code", neighborhood_code)
                .eq("district", district)
                .gt("building_area", 0)
                .gt("appraised_value", 0)
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"AnomalyDetector: DB query failed for neighborhood {neighborhood_code}: {e}")
            return []
