import sys
import os
import unittest

# Ensure backend is on path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.services.valuation_service import ValuationService

class TestValuationService(unittest.TestCase):
    def setUp(self):
        self.service = ValuationService()

    def test_age_adjustment_double_count_fix(self):
        """Verify that Age adjustment is ZERO and only Percent Good is used."""
        subject = {
            "year_built": 2000,
            "building_area": 2000,
            "appraised_value": 500000,
            "quality": "B-"
        }
        comp = {
            "year_built": 1990,
            "building_area": 2000,
            "appraised_value": 450000,
            "quality": "B-"
        }
        
        adj = self.service.calculate_adjustments(subject, comp)
        
        # Age adjustment should be 0 (linear method removed)
        self.assertEqual(adj.get("age"), 0, "Age adjustment should be 0 to avoid double counting")
        
        # Percent Good should be non-zero (assuming different depreciation)
        # 2000 vs 1990 -> 25 vs 35 years old (approx)
        # Depreciation table should yield different % good
        self.assertNotEqual(adj.get("percent_good"), 0, "Percent Good adjustment should be active")
        
        # Verify direction: Subject is newer (less depreciation), so Comp (older) needs UPWARD adjustment?
        # Actually, if Subject is newer, it's worth MORE. Comp is older/worth less.
        # Adjusted Comp Value = Comp Value + (Subject Value - Comp Value due to diff)
        # Meaning: To make the Comp look like the Subject, we add value.
        # Percent Good logic: (subj_pct - comp_pct) / 100 * comp_value
        # Subj (25 yrs) > Comp (35 yrs) => Positive adjustment. Correct.
        self.assertGreater(adj.get("percent_good"), 0)

    def test_size_adjustment(self):
        """Verify 50% diminishing returns rule."""
        subject = {"building_area": 3000, "appraised_value": 600000}
        comp = {"building_area": 2000, "appraised_value": 400000}
        
        # Comp Price/SqFt = 200
        # Diff = +1000 sqft
        # Adj = 1000 * (200 * 0.5) = 1000 * 100 = +100,000
        
        adj = self.service.calculate_adjustments(subject, comp)
        self.assertAlmostEqual(adj.get("size"), 100000, delta=100)

if __name__ == '__main__':
    unittest.main()
