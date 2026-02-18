import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from typing import List, Dict

class EquityAgent:
    def __init__(self):
        self.knn = NearestNeighbors(n_neighbors=20, metric='euclidean')

    def find_equity_5(self, subject_property: Dict, neighborhood_properties: List[Dict]) -> Dict:
        """
        Perform a K-Nearest Neighbors (KNN) search to find the 20 most physically similar neighbors.
        Selection: Sort neighbors by 'Assessed Value per SqFt' ascending. Select the top 5 (The 'Equity 5').
        Calculation: Calculate the median of the Equity 5 to determine the 'Justified Value Floor.'
        """
        subj_val = subject_property.get('appraised_value', 0)
        subj_area = subject_property.get('building_area', 0)
        
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
        
        # Features for KNN: Building Area, Year Built (if available)
        features = ['building_area']
        subject_vals = [subj_area]
        
        if 'year_built' in df.columns and subject_property.get('year_built'):
            # Filter out neighbors with no year_built for this calc
            # Or fill with median as a safeguard
            df['year_built'] = pd.to_numeric(df['year_built'], errors='coerce').fillna(df['year_built'].median() if not df[df['year_built'].notnull()].empty else 1980)
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
        self.knn = NearestNeighbors(n_neighbors=min(20, len(df)), metric='euclidean')
        self.knn.fit(X_scaled)
        distances, indices = self.knn.kneighbors(subject_X_scaled)
        
        # Get the 20 most similar neighbors
        top_20 = df.iloc[indices[0]].copy()
        
        # Add similarity score (Inverse distance with a steeper falloff for better UX)
        # Max distance in [0,1] space for N features is sqrt(N)
        max_dist = np.sqrt(len(features))
        top_20['similarity_score'] = (1 - (distances[0] / max_dist)) * 100
        # Clip to [0, 100]
        top_20['similarity_score'] = top_20['similarity_score'].clip(0, 100)
        
        # Calculate 'Assessed Value per SqFt'
        top_20['value_per_sqft'] = pd.to_numeric(top_20['appraised_value'], errors='coerce') / pd.to_numeric(top_20['building_area'], errors='coerce')
        
        # Sort by value_per_sqft ascending
        top_20_sorted = top_20.sort_values(by='value_per_sqft', ascending=True)
        
        # Select top 5
        equity_5 = top_20_sorted.head(5)
        
        justified_value_floor = equity_5['value_per_sqft'].median() * subj_area
        
        return {
            'equity_5': equity_5.to_dict('records'),
            'justified_value_floor': justified_value_floor,
            'subject_value_per_sqft': subj_val / subj_area
        }
