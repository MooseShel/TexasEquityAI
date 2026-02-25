from typing import List, Dict
import logging
from backend.agents.sales_agent import SalesAgent
from backend.services.valuation_service import valuation_service
from backend.services.adjustment_model import adjustment_model

logger = logging.getLogger(__name__)

class EquityAgent:
    def __init__(self):
        # KNN logic removed: Similarity search is now offloaded to Supabase pgvector
        pass

    def find_equity_5(self, subject_property: Dict, neighborhood_properties: List[Dict]) -> Dict:
        """
        Perform a Vector Similarity search via Supabase pgvector to find the most physically similar neighbors across the city.
        Selection: Sort neighbors by 'Assessed Value per SqFt' ascending. Select the top 5 (The 'Equity 5').
        Calculation: Calculate the median of the Equity 5 to determine the 'Justified Value Floor.'
        Note: The `neighborhood_properties` arg is kept for retro-compatibility but is ignored, as pgvector searches the whole DB.
        """
        from backend.db.vector_store import vector_store
        
        subj_val = subject_property.get('appraised_value', 0) or 0
        subj_area = subject_property.get('building_area', 0) or 0
        subj_pps = (subj_val / subj_area) if subj_area and subj_area > 0 else 0
        
        if not subj_area or subj_area == 0:
            return {
                'equity_5': [],
                'justified_value_floor': subj_val,
                'subject_value_per_sqft': 0,
                'error': "Missing Property Area: Could not perform Square Foot analysis. Using current appraisal as baseline."
            }
            
        logger.info(f"EquityAgent: Executing city-wide pgvector search for {subject_property.get('account_number')}...")
        
        # 1. Fetch the absolute closest 20 physical matches from the entire database
        top_20 = vector_store.find_similar_properties(subject_property, limit=20)
        
        if not top_20 or len(top_20) < 3:
            logger.warning(f"Vector search returned insufficient matches ({len(top_20)}). Returning baseline.")
            return {
                'equity_5': top_20,
                'justified_value_floor': subj_val,
                'subject_value_per_sqft': subj_pps,
                'error': f"Insufficient comparable properties found in DB. Using current appraisal as baseline."
            }

        # 2. Add 'value_per_sqft' to each comp and filter out bad data
        valid_comps = []
        for comp in top_20:
            try:
                area = float(comp.get('building_area') or 0)
                val = float(comp.get('appraised_value') or 0)
                if area > 0 and val > 0:
                    comp['value_per_sqft'] = val / area
                    # similarity is provided by the RPC
                    valid_comps.append(comp)
            except Exception:
                continue
                
        if not valid_comps:
            return {
                'equity_5': [],
                'justified_value_floor': subj_val,
                'subject_value_per_sqft': subj_pps,
                'error': "Could not calculate value per squar foot for returned vector matches."
            }

        # 3. Sort by 'value_per_sqft' ascending (lowest taxed neighbors first)
        valid_comps.sort(key=lambda x: x['value_per_sqft'])
        
        # 4. Select the top 10 for adjustments
        equity_10 = valid_comps[:10]
        
        # Phase 2: Professional Adjustments
        logger.info(f"Applying professional adjustments to {len(equity_10)} vector comps...")
        
        # 4.5. Get Dynamic ML Adjustment Rates
        logger.info("EquityAgent: Fetching dynamic ML adjustment rates for subject neighborhood...")
        local_rates = adjustment_model.get_local_rates(subject_property)
        logger.info(f"EquityAgent: Using adjustment rates: {local_rates}")
        
        adj_values = []
        
        for comp in equity_10:
            try:
                adjustments = valuation_service.calculate_adjustments(subject_property, comp, local_rates)
                comp['adjustments'] = adjustments
                adj_values.append(adjustments['adjusted_value'])
            except Exception as e:
                logger.warning(f"Adjustment calc failed for comp {comp.get('account_number')}: {e}")
                comp['adjustments'] = {}

        # Phase 3: Deed / Sale Recency Enrichment (retro-compatibility)
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")  # 24 months
        recently_sold_count = 0
        for comp in equity_10:
            sale_date = comp.get('last_sale_date')
            if sale_date:
                comp['recently_sold'] = str(sale_date) >= cutoff
                if comp['recently_sold']:
                    recently_sold_count += 1
            else:
                comp['recently_sold'] = False
                
        if recently_sold_count:
            logger.info(f"EquityAgent: {recently_sold_count}/{len(equity_10)} comps have recent deed transfers (< 24mo)")

        # New Justified Value Floor = Median of adjusted total values
        if adj_values:
            adj_values.sort()
            justified_value_floor = adj_values[len(adj_values)//2]
        else:
            justified_value_floor = subj_val

        return {
            'equity_5': equity_10,
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
