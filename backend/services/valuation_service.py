import logging
import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class ValuationService:
    """
    Handles appraisal adjustment logic to normalize comparable properties
    against a subject property. Produces the full professional adjustment grid
    matching the format used in Harris County ARB hearings.
    """

    # Grade mappings (multipliers based on standard appraisal practices)
    GRADE_MAP = {
        'A+': 1.25, 'A': 1.20, 'A-': 1.15,
        'B+': 1.10, 'B': 1.05, 'B-': 1.00,
        'C+': 0.95, 'C': 0.90, 'C-': 0.85,
        'D+': 0.80, 'D': 0.75, 'D-': 0.70,
        'X+': 1.50, 'X': 1.40,  # Luxury
        'S+': 0.65, 'S': 0.60   # Substandard
    }

    # Effective age depreciation schedule (% good remaining)
    # Based on Marshall & Swift residential depreciation tables
    DEPRECIATION_TABLE = {
        0: 100, 1: 99, 2: 98, 3: 97, 4: 96, 5: 95,
        6: 94, 7: 93, 8: 92, 9: 91, 10: 90,
        15: 85, 20: 80, 25: 75, 30: 70, 35: 65,
        40: 60, 45: 55, 50: 50, 60: 40, 70: 30
    }

    def __init__(self):
        pass

    def _get_percent_good(self, year_built) -> int:
        """Calculate % good based on effective age using depreciation schedule."""
        year = self._parse_year(year_built)
        if not year:
            return 80  # Default assumption
        current_year = datetime.datetime.now().year
        age = max(0, current_year - year)
        
        # Interpolate from depreciation table
        keys = sorted(self.DEPRECIATION_TABLE.keys())
        for i in range(len(keys) - 1):
            if keys[i] <= age <= keys[i + 1]:
                lo, hi = keys[i], keys[i + 1]
                lo_val, hi_val = self.DEPRECIATION_TABLE[lo], self.DEPRECIATION_TABLE[hi]
                ratio = (age - lo) / (hi - lo)
                pct_good = int(lo_val - ratio * (lo_val - hi_val))
                break
        else:
            if age >= keys[-1]:
                pct_good = self.DEPRECIATION_TABLE[keys[-1]]
            else:
                pct_good = 100

        # Phase 4: Compound Depreciation Reality Checks
        # Cap total physical depreciation to 90% (meaning minimum % good is 10%)
        return max(10, pct_good)

    def calculate_adjustments(self, subject: Dict, comp: Dict, local_rates: Dict = None) -> Dict:
        """
        Calculate the full professional adjustment grid for a comparable property.
        Returns a dict matching the format used in the sample ARB report.
        Incorporates dynamic ML-derived rates if `local_rates` is provided.
        """
        adjustments = {
            "size": 0,
            "grade": 0,
            "age": 0,
            "remodel": 0,
            "neighborhood": 0,
            "percent_good": 0,
            "lump_sum": 0,
            "sub_area_diff": 0,
            "land_value": 0,
            "segments": 0,
            "other_improvements": 0,
            "deferred_maintenance": 0,
            "total": 0,
            "net_adjustment": 0,
            "indicated_value": 0,
        }

        comp_area = comp.get('building_area') or 0
        subj_area = subject.get('building_area') or 0
        comp_value = comp.get('appraised_value') or comp.get('market_value') or 0
        subj_value = subject.get('appraised_value') or subject.get('market_value') or 0

        # --- 1. Size Adjustment ---
        if comp_area > 0 and subj_area > 0:
            diff = subj_area - comp_area
            # Check for ML-derived size rate first
            if local_rates and "size_rate" in local_rates:
                adj_factor = local_rates["size_rate"]
                logger.debug(f"Using ML size rate: ${adj_factor:.2f}/sf")
            else:
                base_pps = comp_value / comp_area if comp_area > 0 else 0
                adj_factor = base_pps * 0.5  # 50% adjustment rule (legacy fallback)
            
            adjustments["size"] = round(diff * adj_factor)

        # --- 2. Grade Adjustment ---
        subj_grade = str(subject.get('building_grade', 'B-') or 'B-').strip()
        comp_grade = str(comp.get('building_grade', 'B-') or 'B-').strip()

        subj_mult = self.GRADE_MAP.get(subj_grade, 1.0)
        comp_mult = self.GRADE_MAP.get(comp_grade, 1.0)

        if comp_mult > 0:
            grade_diff_pct = (subj_mult / comp_mult) - 1
            adjustments["grade"] = round(comp_value * grade_diff_pct)
        
        # Store grade labels for display
        adjustments["subject_grade"] = subj_grade
        adjustments["comp_grade"] = comp_grade

        # --- 3. Age / Year Built Adjustment ---
        subj_year = self._parse_year(subject.get('year_built'))
        comp_year = self._parse_year(comp.get('year_built'))

        if subj_year and comp_year:
            # We use effective age / depreciation (Marshall & Swift) instead of linear age adjustment
            # to avoid double counting.
            adjustments["age"] = 0

        # --- 4. Remodel Adjustment ---
        subj_remodel = self._parse_year(subject.get('year_remodeled') or subject.get('year_built'))
        comp_remodel = self._parse_year(comp.get('year_remodeled') or comp.get('year_built'))
        adjustments["subject_remodel"] = "New/Rebuilt" if subj_remodel and subj_remodel >= (datetime.datetime.now().year - 5) else str(subj_remodel or "N/A")
        adjustments["comp_remodel"] = str(comp_remodel or "N/A")
        # Remodel adjustment is embedded in age adjustment for simplicity
        adjustments["remodel"] = 0

        # --- 5. Neighborhood Adjustment ---
        subj_nbhd = str(subject.get('neighborhood_code', ''))
        comp_nbhd = str(comp.get('neighborhood_code', ''))
        adjustments["subject_nbhd"] = subj_nbhd
        adjustments["comp_nbhd"] = comp_nbhd
        # Same neighborhood = $0 adjustment
        adjustments["neighborhood"] = 0

        # --- 6. % Good (Depreciation) ---
        subj_pct = self._get_percent_good(subject.get('year_built'))
        comp_pct = self._get_percent_good(comp.get('year_built'))
        adjustments["subject_pct_good"] = subj_pct
        adjustments["comp_pct_good"] = comp_pct
        
        if comp_pct > 0:
            pct_diff = (subj_pct - comp_pct) / 100
            # F-4 Fix: Depreciation applies only to improvement value, not land
            # Per IAAO/Marshall & Swift, land does not depreciate
            comp_improvement = max(0, comp_value - float(comp.get('land_value') or 0))
            adjustments["percent_good"] = round(comp_improvement * pct_diff)

        # --- 6.5. Deferred Maintenance Penalty ---
        # If effective_age > 20 years AND permit_count == 0 AND Vision Agent detects issues
        permit_summary = subject.get('permit_summary')
        vision_summary = subject.get('vision_summary')
        
        current_year = datetime.datetime.now().year
        subj_age = max(0, current_year - self._parse_year(subject.get('year_built')))
        
        deferred_penalty_value = 0
        is_deferred = False
        if subj_age > 20:
            has_permits = permit_summary.get('has_renovations', True) if permit_summary else True
            vision_issues = 0
            if vision_summary:
                vision_issues = len([i for i in vision_summary if isinstance(i, dict) and i.get('issue') and 'CONDITION_SUMMARY' not in i.get('issue')])
            
            if not has_permits and vision_issues > 0:
                # 10% penalty of the comp value
                deferred_penalty_value = round(comp_value * -0.10)
                is_deferred = True

        adjustments["deferred_maintenance"] = deferred_penalty_value
        adjustments["is_deferred"] = is_deferred

        # --- 7. Sub Area Difference ---
        subj_sub_areas = subject.get('sub_areas', 0) or 0
        comp_sub_areas = comp.get('sub_areas', 0) or 0
        if subj_sub_areas and comp_sub_areas:
            adjustments["sub_area_diff"] = round((subj_sub_areas - comp_sub_areas) * 50)  # $50/sf for sub areas

        # --- 8. Land Value Adjustment ---
        subj_land = float(subject.get('land_value') or 0)
        comp_land = float(comp.get('land_value') or 0)
        
        # ML Land Rate Overrides pure Appraised Difference
        if local_rates and "land_rate" in local_rates:
            subj_land_area = float(subject.get('land_area') or 0)
            comp_land_area = float(comp.get('land_area') or 0)
            if subj_land_area > 0 and comp_land_area > 0:
                land_diff = subj_land_area - comp_land_area
                adjustments["land_value"] = round(land_diff * local_rates["land_rate"])
            else:
                adjustments["land_value"] = 0
        else:
            # Fallback to direct assessed land value comparison
            if subj_land and not comp_land:
                # Estimate comp land proportionally by area
                subj_land_area = float(subject.get('land_area') or 1)
                comp_land_area = float(comp.get('land_area') or subj_land_area)
                comp_land = subj_land * (comp_land_area / subj_land_area) if subj_land_area > 0 else subj_land
            adjustments["land_value"] = round(subj_land - comp_land) if subj_land and comp_land else 0
        adjustments["subject_land_value"] = subj_land
        adjustments["comp_land_value"] = comp_land

        # --- 9. Segments & Other Improvements ---
        subj_segments = subject.get('segments_value') or 0
        comp_segments = comp.get('segments_value') or 0
        adjustments["segments"] = round(subj_segments - comp_segments)
        
        subj_other = subject.get('other_improvements') or 0
        comp_other = comp.get('other_improvements') or 0
        adjustments["other_improvements"] = round(subj_other - comp_other)

        # --- Net Adjustment ---
        adjustments["net_adjustment"] = (
            adjustments["size"] + adjustments["grade"] + adjustments["age"] +
            adjustments["remodel"] + adjustments["neighborhood"] + adjustments["percent_good"] +
            adjustments["lump_sum"] + adjustments["sub_area_diff"] + adjustments["land_value"] +
            adjustments["segments"] + adjustments["other_improvements"] + adjustments["deferred_maintenance"]
        )

        # --- Indicated Value = Comp Value + Net Adjustment ---
        # Prevent negative indicated values explicitly
        ind_val = comp_value + adjustments["net_adjustment"]
        adjustments["indicated_value"] = max(1000, ind_val)
        
        # Keep backward compat
        adjustments["total"] = adjustments["net_adjustment"]
        adjustments["adjusted_value"] = adjustments["indicated_value"]

        return adjustments

    def _parse_year(self, year_val) -> int:
        if not year_val: return 0
        try:
            return int(str(year_val)[:4])
        except:
            return 0

    def get_opinion_of_value(self, subject: Dict, adjusted_comps: List[Dict]) -> Dict:
        """
        Aggregate adjusted values from multiple comps to form a final opinion.
        Selection: Typically the median or weighted average of adjusted values.
        """
        if not adjusted_comps:
            return {"opinion": subject.get('appraised_value', 0), "confidence": "low"}

        adj_values = [c['adjustments']['indicated_value'] for c in adjusted_comps]
        adj_values.sort()

        median_adj = adj_values[len(adj_values) // 2]

        return {
            "opinion": median_adj,
            "min_adjusted": adj_values[0],
            "max_adjusted": adj_values[-1],
            "median": median_adj,
            "confidence": "high" if len(adjusted_comps) >= 3 else "medium"
        }


# Singleton
valuation_service = ValuationService()
