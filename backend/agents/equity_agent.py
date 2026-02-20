import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from typing import List, Dict
import logging
from backend.agents.sales_agent import SalesAgent
from backend.services.valuation_service import valuation_service

logger = logging.getLogger(__name__)

class EquityAgent:
    def __init__(self):
        self.knn = NearestNeighbors(n_neighbors=20, metric='euclidean')

    def find_equity_5(self, subject_property: Dict, neighborhood_properties: List[Dict]) -> Dict:
        """
        Perform a K-Nearest Neighbors (KNN) search to find the 20 most physically similar neighbors.
        Selection: Sort neighbors by 'Assessed Value per SqFt' ascending. Select the top 5 (The 'Equity 5').
        Calculation: Calculate the median of the Equity 5 to determine the 'Justified Value Floor.'
        """
        subj_val = subject_property.get('appraised_value', 0) or 0
        subj_area = subject_property.get('building_area', 0) or 0
        
        # If area is 0, we can't perform meaningful SQFT-based analysis
        if not subj_area or subj_area == 0:
            return {
                'equity_5': [],
                'justified_value_floor': subj_val,
                'subject_value_per_sqft': 0,
                'error': "Missing Property Area: Could not perform Square Foot analysis. Using current appraisal as baseline."
            }

        if not neighborhood_properties:
            return {
                'equity_5': [],
                'justified_value_floor': subj_val,
                'subject_value_per_sqft': subj_val / subj_area
            }
        
        # Build DataFrame from neighbor list
        df = pd.DataFrame(neighborhood_properties)
        
        # Ensure required columns exist
        for col in ['building_area', 'appraised_value']:
            if col not in df.columns:
                df[col] = 0
        
        # Convert to numeric, coerce errors to NaN
        df['building_area'] = pd.to_numeric(df['building_area'], errors='coerce').fillna(0)
        df['appraised_value'] = pd.to_numeric(df['appraised_value'], errors='coerce').fillna(0)
        
        # CRITICAL: Filter out neighbors with 0 area (prevents division-by-zero in value_per_sqft)
        df = df[df['building_area'] > 0].copy()
        
        if len(df) < 3:
            logger.warning(f"Only {len(df)} valid neighbors after filtering zero-area properties. Returning baseline.")
            return {
                'equity_5': [],
                'justified_value_floor': subj_val,
                'subject_value_per_sqft': subj_val / subj_area,
                'error': f"Insufficient comparable properties ({len(df)} found after filtering). Using current appraisal as baseline."
            }
        
        # Features for KNN: Building Area, Year Built (if available)
        features = ['building_area']
        subject_vals = [subj_area]
        
        if 'year_built' in df.columns and subject_property.get('year_built'):
            # Convert year_built to numeric, fill missing with median
            df['year_built'] = pd.to_numeric(df['year_built'], errors='coerce')
            median_year = df['year_built'].median() if df['year_built'].notna().any() else 1980
            df['year_built'] = df['year_built'].fillna(median_year)
            features.append('year_built')
            subject_vals.append(subject_property['year_built'])
        
        X = df[features].values
        subject_X = np.array([subject_vals])
        
        # NORMALIZATION: Scale features to [0,1] to ensure Area doesn't drown out Year Built
        X_min = X.min(axis=0)
        X_max = X.max(axis=0)
        # Avoid division by zero
        X_range = np.where((X_max - X_min) == 0, 1, X_max - X_min)
        X_scaled = (X - X_min) / X_range
        subject_X_scaled = (subject_X - X_min) / X_range
        
        # Fit KNN on scaled features
        n_neighbors = min(20, len(df))
        self.knn = NearestNeighbors(n_neighbors=n_neighbors, metric='euclidean')
        self.knn.fit(X_scaled)
        distances, indices = self.knn.kneighbors(subject_X_scaled)
        
        # Get the most similar neighbors
        top_20 = df.iloc[indices[0]].copy()
        
        # Add similarity score (Inverse distance with a steeper falloff for better UX)
        max_dist = np.sqrt(len(features))
        top_20['similarity_score'] = (1 - (distances[0] / max_dist)) * 100
        top_20['similarity_score'] = top_20['similarity_score'].clip(0, 100)
        
        # Calculate 'Assessed Value per SqFt'
        top_20['value_per_sqft'] = (
            pd.to_numeric(top_20['appraised_value'], errors='coerce') /
            pd.to_numeric(top_20['building_area'], errors='coerce')
        )
        
        # Drop any rows where value_per_sqft is NaN or 0
        top_20 = top_20[top_20['value_per_sqft'] > 0].dropna(subset=['value_per_sqft'])
        
        if top_20.empty:
            return {
                'equity_5': [],
                'justified_value_floor': subj_val,
                'subject_value_per_sqft': subj_val / subj_area,
                'error': "Could not calculate value per sqft for any comparable properties."
            }
        
        # Sort by value_per_sqft ascending — lowest-taxed comps first
        top_20_sorted = top_20.sort_values(by='value_per_sqft', ascending=True)
        
        # Select top 10
        equity_5_df = top_20_sorted.head(10).copy()
        
        # Phase 2: Professional Adjustments
        logger.info(f"Applying professional adjustments to {len(equity_5_df)} comps...")
        equity_5_list = equity_5_df.to_dict('records')
        adj_values = []
        
        for comp in equity_5_list:
            try:
                adjustments = valuation_service.calculate_adjustments(subject_property, comp)
                comp['adjustments'] = adjustments
                adj_values.append(adjustments['adjusted_value'])
            except Exception as e:
                logger.warning(f"Adjustment calc failed for comp {comp.get('account_number')}: {e}")
                comp['adjustments'] = {}
        
        # New Justified Value Floor = Median of adjusted total values
        if adj_values:
            adj_values.sort()
            justified_value_floor = adj_values[len(adj_values)//2]
        else:
            justified_value_floor = subj_val

        # Safe calc for subject PPS
        subj_pps = 0
        if subj_area and subj_area > 0:
            subj_pps = subj_val / subj_area

        return {
            'equity_5': equity_5_list,
            'justified_value_floor': justified_value_floor,
            'subject_value_per_sqft': subj_pps
        }

    def get_sales_analysis(self, subject_property: Dict) -> Dict:
        """
        Uses SalesAgent to get Sales Comparables Table.
        """
        try:
            logger.info(f"EquityAgent: Initiating Sales Analysis for {subject_property.get('address', 'Unknown')}...")
            agent = SalesAgent()
            comps = agent.find_sales_comps(subject_property)
            logger.info(f"EquityAgent: Sales Analysis complete. Found {len(comps)} comps.")
            return {
                "sales_comps": comps,
                "sales_count": len(comps)
            }
        except Exception as e:
            logger.error(f"Sales Analysis Failed: {e}")
            return {"sales_comps": [], "sales_count": 0, "error": str(e)}
