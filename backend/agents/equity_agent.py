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
        if not neighborhood_properties:
            return {}

        df = pd.DataFrame(neighborhood_properties)
        
        # Features for KNN: Building Area, Year Built (if available), Lot Size (if available)
        # For MVP: [Building Area]
        features = ['building_area']
        
        X = df[features].values
        subject_X = np.array([[subject_property['building_area']]])
        
        self.knn.fit(X)
        distances, indices = self.knn.kneighbors(subject_X)
        
        # Get the 20 most similar neighbors
        top_20 = df.iloc[indices[0]].copy()
        
        # Calculate 'Assessed Value per SqFt' (using appraised_value as proxy for assessed)
        top_20['value_per_sqft'] = top_20['appraised_value'] / top_20['building_area']
        
        # Sort by value_per_sqft ascending
        top_20_sorted = top_20.sort_values(by='value_per_sqft', ascending=True)
        
        # Select top 5
        equity_5 = top_20_sorted.head(5)
        
        justified_value_floor = equity_5['value_per_sqft'].median() * subject_property['building_area']
        
        return {
            'equity_5': equity_5.to_dict('records'),
            'justified_value_floor': justified_value_floor,
            'subject_value_per_sqft': subject_property['appraised_value'] / subject_property['building_area']
        }
