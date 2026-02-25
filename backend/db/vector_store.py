import logging
import math
from typing import Dict, List, Optional
from backend.db.supabase_client import supabase_service

logger = logging.getLogger(__name__)

class VectorStore:
    """
    Handles calculating 4D property embeddings for pgvector similarity search.
    The 4 dimensions are:
    0: Normalized Building Area
    1: Normalized Year Built
    2: Normalized Building Grade
    3: Normalized Land Area
    """
    
    # Normalization bounds (to keep 0.0 - 1.0)
    MAX_AREA = 10000.0
    MIN_YEAR = 1900.0
    MAX_YEAR = 2025.0
    MAX_LAND = 43560.0 * 5  # 5 acres
    
    # Houston typical grade map to numeric for distance calculation
    GRADE_TO_NUM = {
        'X+': 1.0, 'X': 0.95, 'X-': 0.9,
        'E+': 0.85, 'E': 0.8, 'E-': 0.75,
        'A+': 0.7, 'A': 0.65, 'A-': 0.6,
        'B+': 0.55, 'B': 0.5, 'B-': 0.45,
        'C+': 0.4, 'C': 0.35, 'C-': 0.3,
        'D+': 0.25, 'D': 0.2, 'D-': 0.15,
        'E': 0.1, 'F': 0.05
    }

    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """Min-max scaler bounded between 0 and 1."""
        if not value: return 0.0
        val = min(max(value, min_val), max_val)
        return (val - min_val) / (max_val - min_val)

    def compute_embedding(self, property_data: Dict) -> List[float]:
        """Convert a property dictionary into a 4-dimensional feature vector."""
        
        # 1. Building Area (weighted heavily)
        area = float(property_data.get('building_area') or 0)
        norm_area = self._normalize(area, 0, self.MAX_AREA) * 2.0  # 2x weight for size
        
        # 2. Year Built
        year = float(property_data.get('year_built') or self.MIN_YEAR)
        norm_year = self._normalize(year, self.MIN_YEAR, self.MAX_YEAR) * 1.5  # 1.5x weight for age
        
        # 3. Grade Numeric
        grade_str = str(property_data.get('building_grade', 'C')).upper().strip()
        norm_grade = self.GRADE_TO_NUM.get(grade_str, 0.35)  # Default to 'C' grade
        
        # 4. Land Area
        land = float(property_data.get('land_area') or 0)
        norm_land = self._normalize(land, 0, self.MAX_LAND) * 0.5  # 0.5x weight for lot size
        
        return [norm_area, norm_year, norm_grade, norm_land]

    def update_property_embedding(self, account_number: str, property_data: Dict) -> bool:
        """Compute and save the embedding for a property to Supabase."""
        try:
            embedding = self.compute_embedding(property_data)
            
            # Format as pgvector array string: '[0.1, 0.2, 0.3, 0.4]'
            emb_str = f"[{','.join(f'{x:.4f}' for x in embedding)}]"
            
            response = supabase_service.client.table("properties") \
                .update({"embedding": emb_str}) \
                .eq("account_number", account_number) \
                .execute()
                
            return bool(response.data)
        except Exception as e:
            logger.error(f"Failed to update embedding for {account_number}: {e}")
            return False

    def find_similar_properties(self, subject: Dict, limit: int = 15) -> List[Dict]:
        """
        Query Supabase to find properties physically similar to the subject.
        Replaces the old Pandas/Scikit-learn KNN logic.
        """
        if not supabase_service.client:
            logger.warning("VectorStore: Supabase client not initialized.")
            return []
            
        try:
            # 1. Calculate subject vector
            subject_vec = self.compute_embedding(subject)
            emb_str = f"[{','.join(f'{x:.4f}' for x in subject_vec)}]"
            
            # Use RPC call for exact distance sorting, or just let Supabase match.
            # Fast raw SQL via Supabase RPC function (we need to create match_properties):
            # Because raw vector ops are best done in a postgres function.
            
            # Wait - if we haven't created the RPC, we can query via PostgREST if it supports <->.
            # Actually, standard PostgREST doesn't support vector distance ordering directly without an RPC function.
            # So, we'll need a fallback RPC instruction or implement client-side computation.
            
            # Let's request the RPC function here for the db migration.
            rpc_params = {
                'query_embedding': emb_str,
                'match_threshold': 0.5, # adjust based on L2 space
                'match_count': limit,
                # Filter by same district and roughly same property type
                'p_district': subject.get('district', 'HCAD')
            }
            
            logger.info(f"VectorStore: Querying match_properties for {subject.get('account_number')}...")
            response = supabase_service.client.rpc("match_properties", rpc_params).execute()
            
            if response.data:
                logger.info(f"VectorStore: Found {len(response.data)} similar properties via pgvector.")
                return response.data
            else:
                logger.warning("VectorStore: No similar properties returned from RPC.")
                return []
                
        except Exception as e:
            logger.error(f"VectorStore: match_properties failed: {e}")
            return []

vector_store = VectorStore()
