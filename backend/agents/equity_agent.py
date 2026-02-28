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
            # Commercial properties often lack building_area.
            # If we have neighborhood comps passed in, use them with raw appraised value comparison.
            if neighborhood_properties and len(neighborhood_properties) >= 3:
                logger.info(f"EquityAgent: No building_area — using {len(neighborhood_properties)} passed-in comps with value-only comparison")
                valid_comps = []
                for comp in neighborhood_properties:
                    try:
                        val = float(comp.get('appraised_value') or 0)
                        area = float(comp.get('building_area') or 0)
                        if val > 0:
                            comp['value_per_sqft'] = (val / area) if area > 0 else 0
                            comp['comp_source'] = 'local'
                            
                            # Calculate a heuristic similarity score based on value and area
                            # since we don't have embeddings for these comps.
                            sim_penalty = 0.0
                            if area > 0 and subj_area > 0:
                                sim_penalty += abs(area - subj_area) / max(area, subj_area)
                            else:
                                sim_penalty += 0.5 # Unknown building area penalty
                                
                            val_diff = abs(val - subj_val) / max(val, subj_val, 1)
                            sim_penalty += val_diff * 0.5
                            
                            comp['similarity'] = max(0.01, min(1.0, 1.0 - sim_penalty))
                                
                            valid_comps.append(comp)
                    except Exception:
                        continue
                
                if valid_comps:
                    # Sort by appraised value ascending (lowest-valued neighbors first)
                    valid_comps.sort(key=lambda x: float(x.get('appraised_value', 0)))
                    equity_10 = valid_comps[:10]
                    
                    # Calculate justified value floor as median of comp appraised values
                    comp_values = [float(c.get('appraised_value', 0)) for c in equity_10 if float(c.get('appraised_value', 0)) > 0]
                    if comp_values:
                        comp_values.sort()
                        justified_value_floor = comp_values[len(comp_values) // 2]
                    else:
                        justified_value_floor = subj_val
                    
                    return {
                        'equity_5': equity_10,
                        'justified_value_floor': justified_value_floor,
                        'subject_value_per_sqft': 0,
                        'equity_analysis_status': 'success' if justified_value_floor < subj_val else 'no_gap',
                        'equity_analysis_reason': '' if justified_value_floor < subj_val else 'No equity gap detected (value-only comparison).',
                        'note': 'Value-only comparison (no sqft data available for subject property)'
                    }
            
            return {
                'equity_5': [],
                'justified_value_floor': subj_val,
                'subject_value_per_sqft': 0,
                'equity_analysis_status': 'failed',
                'equity_analysis_reason': 'Missing property area. Could not perform square foot analysis.',
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
        
        # Exclude the subject property itself from the comp pool.
        # pgvector returns the subject as its own nearest neighbor (similarity ≈ 1.0).
        subj_acct = str(subject_property.get('account_number', '')).strip()
        if wide_pool and subj_acct:
            before_len = len(wide_pool)
            wide_pool = [c for c in wide_pool if str(c.get('account_number', '')).strip() != subj_acct]
            if len(wide_pool) < before_len:
                logger.info(f"EquityAgent: Excluded subject property ({subj_acct}) from its own comp pool")
        
        # ALWAYS merge passed-in DB neighborhood comps into the pgvector pool.
        # pgvector embedding coverage may be incomplete (backfill is incremental),
        # but get_neighbors_from_db always returns full local neighborhood results.
        # Without this merge, local comps get discarded and city-wide comps dominate.
        if neighborhood_properties and len(neighborhood_properties) >= 3:
            existing_accts = {c.get('account_number') for c in (wide_pool or [])}
            subj_year = int(str(subject_property.get('year_built', 0))[:4]) if subject_property.get('year_built') else 0
            
            merged_count = 0
            for comp in neighborhood_properties:
                if comp.get('account_number') in existing_accts:
                    continue  # Already in pgvector results — skip duplicate
                
                # Compute heuristic similarity for DB-only comps (pgvector didn't return these)
                area = float(comp.get('building_area') or 0)
                sim_penalty = 0.0
                if area > 0 and subj_area > 0:
                    sim_penalty += abs(area - subj_area) / max(area, subj_area)
                
                comp_year = int(str(comp.get('year_built', 0))[:4]) if comp.get('year_built') else 0
                if comp_year and subj_year:
                    age_diff = abs(subj_year - comp_year)
                    sim_penalty += min(0.3, age_diff * 0.01)
                    
                comp['similarity'] = max(0.01, min(1.0, 1.0 - sim_penalty))
                
                if wide_pool is None:
                    wide_pool = []
                wide_pool.append(comp)
                existing_accts.add(comp.get('account_number'))
                merged_count += 1
            
            if merged_count:
                logger.info(f"EquityAgent: Merged {merged_count} DB neighborhood comps into pgvector pool "
                            f"(total pool now {len(wide_pool)})")
        
        if not wide_pool or len(wide_pool) < 3:
            logger.warning(f"Vector search + DB merge returned insufficient matches ({len(wide_pool) if wide_pool else 0}). "
                           f"Returning baseline.")
            return {
                'equity_5': wide_pool or [],
                'justified_value_floor': subj_val,
                'subject_value_per_sqft': subj_pps,
                'equity_analysis_status': 'failed',
                'equity_analysis_reason': 'Insufficient comparable properties found in database.',
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
                'equity_analysis_status': 'failed',
                'equity_analysis_reason': 'Could not calculate value per square foot for returned vector matches.',
                'error': "Could not calculate value per square foot for returned vector matches."
            }

        # Phase 2: Professional Adjustments — apply to ALL valid comps (unbiased)
        logger.info(f"Applying professional adjustments to {len(valid_comps)} vector comps...")
        
        # 4.5. Get Dynamic ML Adjustment Rates
        logger.info("EquityAgent: Fetching dynamic ML adjustment rates for subject neighborhood...")
        local_rates = adjustment_model.get_local_rates(subject_property)
        logger.info(f"EquityAgent: Using adjustment rates: {local_rates}")
        
        adj_values = []
        
        for comp in valid_comps:
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
        for comp in valid_comps:
            sale_date = comp.get('last_sale_date')
            if sale_date:
                comp['recently_sold'] = str(sale_date) >= cutoff
                if comp['recently_sold']:
                    recently_sold_count += 1
            else:
                comp['recently_sold'] = False
                
        if recently_sold_count:
            logger.info(f"EquityAgent: {recently_sold_count}/{len(valid_comps)} comps have recent deed transfers (< 24mo)")

        # F-1 Fix: Justified Value Floor = UNBIASED median of ALL adjusted values
        # Uses the full pool of valid comps, not just the lowest-valued subset.
        # This complies with §42.26(a)(3): "median appraised value of a reasonable
        # number of comparable properties appropriately adjusted."
        equity_analysis_status = 'success'
        equity_analysis_reason = ''
        
        if adj_values:
            adj_values.sort()
            justified_value_floor = adj_values[len(adj_values)//2]
            logger.info(f"EquityAgent: Unbiased median of {len(adj_values)} adjusted values = ${justified_value_floor:,.0f}")
        else:
            justified_value_floor = subj_val
            equity_analysis_status = 'failed'
            equity_analysis_reason = 'Professional adjustments could not be computed for any comparable.'

        # F-2: If justified_value_floor equals subj_val due to median being higher,
        # that's a legitimate result (comps support the appraised value), not a failure.
        if equity_analysis_status == 'success' and justified_value_floor >= subj_val:
            equity_analysis_status = 'no_gap'
            equity_analysis_reason = 'Comparable properties support the current appraised value. No equity gap detected.'
            justified_value_floor = subj_val  # Cap at appraised — can't argue for increase

        # 3. Sort by value_per_sqft ascending for DISPLAY only (advocacy presentation)
        valid_comps.sort(key=lambda x: x.get('value_per_sqft', 0))
        
        # Select top 10 for display
        equity_10 = valid_comps[:10]

        return {
            'equity_5': equity_10,
            'justified_value_floor': justified_value_floor,
            'subject_value_per_sqft': subj_pps,
            'equity_analysis_status': equity_analysis_status,
            'equity_analysis_reason': equity_analysis_reason,
            'adjustment_method': local_rates.get('method', 'Default'),
            'adjustment_r2': local_rates.get('r2_score', 0),
        }

    def get_sales_analysis(self, subject_property: Dict) -> Dict:
        """
        Uses SalesAgent to get Sales Comparables, then enriches each comp
        via Supabase lookup and applies professional adjustments.
        
        Returns adjusted sale prices alongside raw sale prices.
        """
        try:
            logger.info(f"EquityAgent: Initiating Sales Analysis for {subject_property.get('address', 'Unknown')}...")
            agent = SalesAgent()
            comps = agent.find_sales_comps(subject_property)
            logger.info(f"EquityAgent: Sales Analysis complete. Found {len(comps)} comps.")
            
            if not comps:
                return {"sales_comps": [], "sales_count": 0, "adjusted_sales_median": 0}
            
            # ── Enrich + Adjust Sales Comps ──────────────────────────────────
            from backend.db.supabase_client import supabase_service
            from backend.services.valuation_service import valuation_service
            from backend.services.adjustment_model import adjustment_model
            
            # Get ML adjustment rates from the subject's neighborhood
            local_rates = adjustment_model.get_local_rates(subject_property)
            logger.info(f"EquityAgent: Sales adjustment rates: {local_rates}")
            
            adjusted_values = []
            enriched_count = 0
            
            for comp in comps:
                # Parse the raw sale price from formatted string
                raw_price_str = str(comp.get("Sale Price", "0")).replace("$", "").replace(",", "").replace("(est)", "").strip()
                try:
                    raw_price = float(raw_price_str)
                except (ValueError, TypeError):
                    raw_price = 0
                
                if raw_price <= 0:
                    continue
                
                # Parse sqft
                sqft_str = str(comp.get("SqFt", "0")).replace(",", "").strip()
                try:
                    sqft = float(sqft_str) if sqft_str != "N/A" else 0
                except (ValueError, TypeError):
                    sqft = 0
                
                # Try to enrich from Supabase by address
                comp_address = comp.get("Address", "")
                enriched_data = {}
                
                if comp_address and supabase_service.client:
                    try:
                        # Extract street portion for matching
                        street_part = comp_address.split(",")[0].strip()
                        clean_street = "".join(c for c in street_part if c.isalnum() or c.isspace()).strip()
                        
                        if len(clean_street) >= 4:
                            response = supabase_service.client.table("properties") \
                                .select("account_number, building_area, year_built, building_grade, "
                                        "land_value, neighborhood_code, appraised_value, land_area, "
                                        "segments_value, other_improvements, sub_areas") \
                                .ilike("address", f"%{clean_street}%") \
                                .limit(1) \
                                .execute()
                            
                            if response.data:
                                enriched_data = response.data[0]
                                enriched_count += 1
                    except Exception as e:
                        logger.debug(f"Supabase lookup failed for '{comp_address}': {e}")
                
                # Build a normalized comp dict for calculate_adjustments
                # Use enriched data for fields not available in sales API, 
                # but prefer the sale price as the comp's "value"
                norm_comp = {
                    "appraised_value": raw_price,  # Use sale price as the base value
                    "building_area": enriched_data.get("building_area") or sqft or 0,
                    "year_built": enriched_data.get("year_built") or comp.get("Year Built") or 0,
                    "building_grade": enriched_data.get("building_grade") or "B-",
                    "land_value": enriched_data.get("land_value") or 0,
                    "land_area": enriched_data.get("land_area") or 0,
                    "neighborhood_code": enriched_data.get("neighborhood_code") or "",
                    "segments_value": enriched_data.get("segments_value") or 0,
                    "other_improvements": enriched_data.get("other_improvements") or 0,
                    "sub_areas": enriched_data.get("sub_areas") or 0,
                }
                
                # Apply full professional adjustment grid
                try:
                    adjustments = valuation_service.calculate_adjustments(
                        subject_property, norm_comp, local_rates
                    )
                    adjusted_sale_price = adjustments.get("indicated_value", raw_price)
                    comp["adjustments"] = adjustments
                    comp["Adjusted Sale Price"] = f"${adjusted_sale_price:,.0f}"
                    comp["_adjusted_value"] = adjusted_sale_price
                    comp["_enriched"] = bool(enriched_data)
                    adjusted_values.append(adjusted_sale_price)
                except Exception as e:
                    logger.warning(f"Sales adjustment failed for {comp_address}: {e}")
                    comp["Adjusted Sale Price"] = comp.get("Sale Price", "N/A")
                    comp["_adjusted_value"] = raw_price
                    comp["_enriched"] = False
                    adjusted_values.append(raw_price)
            
            # Calculate adjusted median
            adjusted_sales_median = 0
            if adjusted_values:
                adjusted_values.sort()
                adjusted_sales_median = adjusted_values[len(adjusted_values) // 2]
            
            logger.info(
                f"EquityAgent: Sales enrichment complete. "
                f"{enriched_count}/{len(comps)} enriched via Supabase. "
                f"Adjusted median: ${adjusted_sales_median:,.0f}"
            )
            
            return {
                "sales_comps": comps,
                "sales_count": len(comps),
                "adjusted_sales_median": adjusted_sales_median,
                "sales_enriched_count": enriched_count,
                "sales_adjustment_method": local_rates.get("method", "Default"),
            }
        except Exception as e:
            logger.error(f"Sales Analysis Failed: {e}")
            return {"sales_comps": [], "sales_count": 0, "adjusted_sales_median": 0, "error": str(e)}
