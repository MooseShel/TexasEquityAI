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
        
        subj_nbhd = str(subject_property.get('neighborhood_code', '')).strip()
        
        # TWO-PASS NEIGHBORHOOD PREFERENCE STRATEGY
        # 1. Fetch a wider pool (40 matches) from the entire database
        # 2. Partition into same-neighborhood (local) vs city-wide pools
        # 3. Prefer local comps; fill remaining slots from city-wide
        #
        # ARB panels strongly prefer same-neighborhood comparables. This approach
        # ensures we prioritize local comps while maintaining a fallback for
        # neighborhoods with sparse data coverage.
        
        wide_pool = vector_store.find_similar_properties(subject_property, limit=40)
        
        if not wide_pool or len(wide_pool) < 3:
            logger.warning(f"Vector search returned insufficient matches ({len(wide_pool) if wide_pool else 0}). Returning baseline.")
            return {
                'equity_5': wide_pool or [],
                'justified_value_floor': subj_val,
                'subject_value_per_sqft': subj_pps,
                'error': f"Insufficient comparable properties found in DB. Using current appraisal as baseline."
            }
        
        # Partition into local (same neighborhood) and city-wide pools
        local_pool = []
        citywide_pool = []
        
        # Extract base neighborhood code (e.g., '8014' from '8014.00') to treat
        # sub-groupings as the same local neighborhood.
        subj_base_nbhd = subj_nbhd.split('.')[0] if subj_nbhd else ''
        
        for comp in wide_pool:
            comp_nbhd = str(comp.get('neighborhood_code', '')).strip()
            comp_base_nbhd = comp_nbhd.split('.')[0] if comp_nbhd else ''
            
            if subj_base_nbhd and comp_base_nbhd == subj_base_nbhd:
                comp['comp_source'] = 'local'
                local_pool.append(comp)
            else:
                comp['comp_source'] = 'city-wide'
                citywide_pool.append(comp)
        
        logger.info(f"EquityAgent: Neighborhood preference split — {len(local_pool)} local ({subj_nbhd}), {len(citywide_pool)} city-wide")
        
        # AGE-PROXIMITY FILTER: Reject comps with year_built >20 years from subject
        # ARB panels dismiss comps from a completely different era (e.g., 1940s vs 2018)
        subj_year = 0
        try:
            subj_year = int(str(subject_property.get('year_built') or 0)[:4])
        except (ValueError, TypeError):
            pass
        
        MAX_YEAR_GAP = 20  # years
        
        def filter_by_age(pool):
            """Filter comps by age proximity. Keeps age-compatible comps first, then appends distant ones as fallback."""
            if not subj_year or subj_year < 1900:
                return pool  # Can't filter without subject year
            
            age_compatible = []
            age_distant = []
            for comp in pool:
                comp_year = 0
                try:
                    comp_year = int(str(comp.get('year_built') or 0)[:4])
                except (ValueError, TypeError):
                    pass
                
                if comp_year and comp_year > 1900 and abs(comp_year - subj_year) > MAX_YEAR_GAP:
                    age_distant.append(comp)
                    logger.debug(f"  Age filter: {comp.get('address', '?')} built {comp_year} (gap={abs(comp_year - subj_year)}yr) — demoted")
                else:
                    age_compatible.append(comp)
            
            if age_distant:
                logger.info(f"EquityAgent: Age filter demoted {len(age_distant)} comps with >{MAX_YEAR_GAP}yr gap from subject (built {subj_year})")
            
            return age_compatible + age_distant  # Compatible first, distant as fallback
        
        local_pool = filter_by_age(local_pool)
        citywide_pool = filter_by_age(citywide_pool)
        
        # Select: prefer local comps; only use city-wide if local pool is insufficient
        # ARB panels strongly prefer same-neighborhood comps — city-wide comps from 
        # Pasadena/Cypress etc. weaken the argument. Only use them as a last resort.
        MIN_LOCAL_THRESHOLD = 5  # If we have ≥5 local, skip city-wide entirely
        TARGET_COMPS = 10
        MAX_LOCAL = 10
        
        selected = local_pool[:MAX_LOCAL]
        
        if len(selected) < MIN_LOCAL_THRESHOLD:
            # Not enough local comps — fill with city-wide
            remaining_slots = TARGET_COMPS - len(selected)
            if remaining_slots > 0:
                selected.extend(citywide_pool[:remaining_slots])
                logger.info(f"EquityAgent: Only {len(local_pool)} local comps — filling {min(remaining_slots, len(citywide_pool))} from city-wide pool")
        else:
            logger.info(f"EquityAgent: {len(selected)} local comps available — skipping city-wide pool entirely")
        
        top_20 = selected
        logger.info(f"EquityAgent: Final selection: {len([c for c in top_20 if c.get('comp_source') == 'local'])} local + "
                     f"{len([c for c in top_20 if c.get('comp_source') == 'city-wide'])} city-wide comps")

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
