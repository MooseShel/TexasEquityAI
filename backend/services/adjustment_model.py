import logging
import numpy as np
from sklearn.linear_model import Ridge
from typing import Dict
from backend.db.vector_store import vector_store

logger = logging.getLogger(__name__)

class AdjustmentModel:
    def __init__(self):
        pass

    def get_local_rates(self, subject: Dict) -> Dict:
        """
        Dynamically calculates ML-derived marginal adjustment rates using Ridge Regression
        on the most similar properties in the local market.
        
        Returns a dictionary with dynamic adjustment rates (e.g., $ per sqft, $ per year built).
        """
        # Default rates if regression fails or yields poor R^2
        default_rates = {
            "size_rate": 50.0,      # $50 / sqft
            "age_rate": 1000.0,     # $1,000 / year built
            "land_rate": 5.0,       # $5 / sqft of land
            "r2_score": 0.0,
            "method": "Default (Fallback)"
        }

        try:
            # 1. Fetch 50 locally similar comps via pgvector
            logger.info(f"AdjustmentModel: Fetching comps for ML regression on account {subject.get('account_number')}")
            comps = vector_store.find_similar_properties(subject, limit=50)
            
            if len(comps) < 10:
                logger.warning(f"AdjustmentModel: Only {len(comps)} comps found. Using default rates.")
                return default_rates

            # 2. Extract features (X) and target (y = appraised_value)
            X = []
            y = []
            
            for c in comps:
                area = float(c.get('building_area') or 0)
                year = float(c.get('year_built') or 1980)
                land = float(c.get('land_area') or 0)
                val = float(c.get('appraised_value') or 0)
                
                if area > 0 and val > 0:
                    y.append(val)
                    X.append([area, year, land])
            
            if len(X) < 10:
                logger.warning("AdjustmentModel: Not enough valid numerical data for regression.")
                return default_rates

            X_np = np.array(X)
            y_np = np.array(y)

            # 3. Fit Ridge Regression (L2 regularization handles multi-collinearity well)
            # Alpha = 10.0 provides strong smoothing to prevent wild coefficient swings
            model = Ridge(alpha=10.0)
            model.fit(X_np, y_np)
            
            coefs = model.coef_
            r2 = model.score(X_np, y_np)
            
            logger.info(f"AdjustmentModel: Fitted regression with R^2 = {r2:.3f}")

            # 4. Extract marginal rates and apply sensible boundaries
            # Size (SqFt): Expect $10 to $500
            raw_size = coefs[0]
            size_rate = max(10.0, min(500.0, float(raw_size)))
            
            # Age (Year): Expect $500 to $5000 per year newer
            # Because year_built is absolute (e.g. 2005 vs 2000), a positive coef means newer is more valuable
            raw_age = coefs[1] 
            age_rate = max(0.0, min(5000.0, float(raw_age)))
            
            # Land (SqFt): Expect $1 to $50
            raw_land = coefs[2]
            land_rate = max(1.0, min(50.0, float(raw_land)))

            return {
                "size_rate": round(size_rate, 2),
                "age_rate": round(age_rate, 2),
                "land_rate": round(land_rate, 2),
                "r2_score": round(float(r2), 3),
                "method": "ML Ridge Regression (Local Comps)"
            }

        except Exception as e:
            logger.error(f"AdjustmentModel failed: {e}")
            return default_rates

adjustment_model = AdjustmentModel()
