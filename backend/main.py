from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import logging
import sys
import asyncio
import traceback
import random
import os
import json
import re

logger = logging.getLogger(__name__)

# MUST be set before any subprocess/playwright calls on Windows
if sys.platform == 'win32':
    logging.info("Attempting to set ProactorEventLoopPolicy...")
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()

from backend.agents.district_factory import DistrictConnectorFactory
from backend.agents.non_disclosure_bridge import NonDisclosureBridge
from backend.agents.equity_agent import EquityAgent
from backend.agents.vision_agent import VisionAgent
from backend.services.narrative_pdf_service import NarrativeAgent, PDFService
from backend.db.supabase_client import supabase_service
from backend.services.hcad_form_service import HCADFormService
from backend.agents.fema_agent import FEMAAgent
from backend.agents.permit_agent import PermitAgent
from backend.agents.commercial_enrichment_agent import CommercialEnrichmentAgent
from backend.agents.anomaly_detector import AnomalyDetectorAgent



# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Texas Equity AI API")

# Initialize Agents
# scraper = HCADScraper() # Replaced by factory in endpoint
factory = DistrictConnectorFactory()
bridge = NonDisclosureBridge()
equity_engine = EquityAgent()
vision_agent = VisionAgent()
narrative_agent = NarrativeAgent()
pdf_service = PDFService()
form_service = HCADFormService()
fema_agent = FEMAAgent()
permit_agent = PermitAgent()
commercial_agent = CommercialEnrichmentAgent()
anomaly_agent = AnomalyDetectorAgent()



@app.get("/")
async def root():
    return {"message": "Texas Equity AI API is running"}

from backend.utils.address_utils import normalize_address, is_real_address



@app.get("/protest/{account_number}")
async def get_full_protest(
    account_number: str,
    manual_address: Optional[str] = None,
    manual_value: Optional[float] = None,
    manual_area: Optional[float] = None,
    district: Optional[str] = None
):
    loop = asyncio.get_running_loop()
    logger.info(f"Current Running Loop Type: {type(loop)}")
    
    if sys.platform == 'win32' and not isinstance(loop, asyncio.WindowsProactorEventLoopPolicy):
         # We can't actually change the running loop here, but we can log it.
         pass

    def _is_ghost_record(p: dict) -> bool:
        """
        Returns True if a DB/scraper record contains known placeholder values or is an empty stub.
        Ghost conditions:
        1. Exact hardcoded mock: appraised=450000, area=2500, no year, no nbhd
        2. Empty stub: appraised <= 1 and area <= 1 (scraper crashed but returned dict)
        """
        if not p:
            return True
        val  = float(p.get('appraised_value') or 0)
        area = float(p.get('building_area') or 0)
        has_year       = bool(p.get('year_built'))
        has_nbhd       = bool(p.get('neighborhood_code'))
        
        # 1. Check for explicit mock fallback
        is_mock = (val == 450000.0 and area == 2500.0 and not has_year and not has_nbhd)
        # 2. Check for empty stub
        is_stub = (val <= 1.0 and area <= 1.0)
        
        return is_mock or is_stub
            
    async def protest_generator():
        print("DEBUG: protest_generator STARTED!")
        try:
            yield json.dumps({"status": "🔍 Resolver Agent: Locating property and resolving address..."}) + "\n"
            
            # 0. Fast DB Address Resolution (Cost-saving optimization)
            current_account = account_number
            current_district = district
            rentcast_fallback_data = None
            resolved_from_db = False

            # Heuristic: If input has spaces and letters, treat as address
            is_address_input = any(c.isalpha() for c in current_account) and " " in current_account

            if is_address_input:
                logger.info(f"Input '{current_account}' detected as address. Searching local database first...")
                try:
                    candidates = await supabase_service.search_address_globally(current_account)
                    if candidates:
                        best = candidates[0]
                        if best.get('district') and best.get('account_number'):
                            new_dist = best['district']
                            new_acc = best['account_number']
                            logger.info(f"Global Address Match (DB): '{current_account}' -> {new_dist} Account #{new_acc} ({best['address']})")
                            
                            if new_dist != current_district:
                                logger.info(f"Address-Correcting district from {current_district} to {new_dist}")
                                current_district = new_dist
                            
                            # CRITICAL: Switch to the real account number!
                            current_account = new_acc
                            resolved_from_db = True
                except Exception as e:
                    logger.warning(f"Global Address Lookup (DB) failed: {e}")

            # 0a. Fallback Address Resolution (RentCast Enabled) if DB miss
            if is_address_input and not resolved_from_db:
                logger.info(f"No local DB match for '{account_number}'. Falling back to RentCast resolution...")
                resolved = await bridge.resolve_address(account_number)
                if resolved:
                    resolved_account = resolved.get('account_number')
                    resolved_ptype   = (resolved.get('rentcast_data') or {}).get('propertyType', '')
                    is_residential_resolve = resolved_ptype in ('Single Family', 'Condo', 'Townhouse', 'Residential')

                    # Only switch current_account if we got a real assessorID back
                    if resolved_account:
                        current_account = resolved_account
                        yield json.dumps({"status": f"✅ Resolver [RentCast]: Found account ID {current_account} (confidence 100%)"}) + "\n"
                        logger.info(f"Resolved address to account: {current_account} via RentCast")
                    else:
                        logger.info(f"RentCast resolve returned no assessorID — keeping original input as account key.")

                    # Only use as fallback data if it's NOT a confirmed residential with no assessorID
                    if resolved_account or not is_residential_resolve:
                        rentcast_fallback_data = resolved
                    else:
                        logger.info(f"Skipping rentcast_fallback_data: residential propertyType='{resolved_ptype}' but no assessorID.")

                    # Infer district from resolved address to ensure correct connector usage
                    if not current_district:
                        res_addr = resolved.get('address', '').lower()
                        if "dallas" in res_addr: current_district = "DCAD"
                        elif "austin" in res_addr: current_district = "TCAD"
                        elif "fort worth" in res_addr: current_district = "TAD"
                        elif "plano" in res_addr: current_district = "CCAD"
                        elif "houston" in res_addr: current_district = "HCAD"
                        if current_district:
                            logger.info(f"Inferred district from RentCast address: {current_district}")

            # 0b. Account Pattern Auto-Correction
            # Even if the user selected a district, the account number format might prove them wrong.
            detected_district = DistrictConnectorFactory.detect_district_from_account(current_account)
            if detected_district and detected_district != current_district:
                logger.info(f"Auto-correcting district from {current_district} to {detected_district} based on account format.")
                current_district = detected_district

            # 0c. Global DB Lookup (Layer 2) — PROOF OF LIFE
            # If the user selected a district but the account exists in another known district in our DB, trust the DB.
            try:
                # We use get_property_by_account which is district-agnostic (by account_number PK)
                db_record = await supabase_service.get_property_by_account(current_account)
                if db_record and db_record.get('district'):
                    db_dist = db_record.get('district')
                    if db_dist != current_district:
                        logger.info(f"DB-Correcting district from {current_district} to {db_dist} (found in confirmed records).")
                        current_district = db_dist
            except Exception as e:
                logger.warning(f"Global DB lookup failed during district check: {e}")


            # 0e. Early Property Type Detection
            yield json.dumps({"status": "🏢 Profiling property type..."}) + "\n"
            from backend.agents.property_type_resolver import resolve_property_type
            original_address = account_number if any(c.isalpha() for c in account_number) else None
            lookup_addr = original_address or account_number
            ptype, ptype_source = await resolve_property_type(current_account, lookup_addr, current_district or "HCAD")
            logger.info(f"Early Type Detection: '{ptype}' via {ptype_source}")
            
            # --- COMMERCIAL FAST PATH ---
            # If we explicitly know it's commercial, bypass the district scraper entirely and go to enrichment.
            fast_commercial_property = None
            if ptype == "Commercial" and not manual_value and not manual_address:
                yield json.dumps({"status": "🏢 Commercial Fast Path: Bypassing district scraper..."}) + "\n"
                enriched = await commercial_agent.enrich_property(lookup_addr)
                if enriched and (enriched.get('appraised_value', 0) > 0 or enriched.get('building_area', 0) > 0):
                    fast_commercial_property = {
                        "account_number": current_account,
                        "district": current_district or "HCAD",
                        "property_type": "commercial",
                        "ptype_source": ptype_source,
                        **enriched
                    }
                    logger.info(f"Fast Path successful: appraised=${fast_commercial_property.get('appraised_value',0):,.0f}, area={fast_commercial_property.get('building_area',0)} sqft")
            
            if fast_commercial_property:
                property_details = fast_commercial_property
                # Skip scraper block
                # Log to the user that we are using the enrichment API instead of the district site
                yield json.dumps({"status": "⛏️ Data Mining Agent: Retrieving commercial details from national databases..."}) + "\n"
                
                # Still need some empty assignment for the below block to not break
                connector = DistrictConnectorFactory.get_connector(current_district or "HCAD", current_account)
                original_address = lookup_addr
            else:
                yield json.dumps({"status": "⛏️ Data Mining Agent: Scraping HCAD records..."}) + "\n"
                
                # 1. Cache & Scrape — DB-first for ALL districts
                cached_property = await supabase_service.get_property_by_account(current_account)

                # Use Factory to get the correct connector
                connector = DistrictConnectorFactory.get_connector(current_district, current_account)
                original_address = account_number if any(c.isalpha() for c in account_number) else None
                
                # Use cached data directly if it has REAL content — skip scraper entirely
                # Ghost/placeholder records (appraised=450k, area=2500, no year/nbhd) are rejected
                if (cached_property
                        and cached_property.get('address')
                        and cached_property.get('appraised_value')
                        and not _is_ghost_record(cached_property)
                        and not manual_value and not manual_address):
                    logger.info(f"DB-first: Using Supabase cached record for {current_account} — skipping scraper.")
                    property_details = cached_property
                else:
                    # Scrape if cache was insufficient
                    try:
                        property_details = await connector.get_property_details(current_account, address=original_address)
                    except Exception as e:
                        logger.error(f"Scraper failed for {current_account}: {e}")
                        property_details = None

                # Fallback: If scraper failed but we had a REAL (non-ghost) partial DB record, use it
                if not property_details and cached_property and not _is_ghost_record(cached_property):
                    logger.warning(f"Scraper failed/returned empty, falling back to cached DB record for {current_account}.")
                    property_details = cached_property

                # CRITICAL: Update current_account if the scraper found the real numeric account
                if property_details and property_details.get('account_number'):
                    scraped_acc = property_details.get('account_number')
                    if scraped_acc != current_account:
                        logger.info(f"Updating account alias: {current_account} -> {scraped_acc}")
                        current_account = scraped_acc

                if not property_details:
                    if rentcast_fallback_data:
                         property_details = rentcast_fallback_data
                    else:
                        # District-aware City Mapping
                        district_map = {
                            "HCAD": "Houston, TX",
                            "TCAD": "Austin, TX",
                            "DCAD": "Dallas, TX",
                            "CCAD": "Plano, TX",
                            "TAD": "Fort Worth, TX"
                        }
                        district_city = district_map.get(current_district, "Houston, TX")

                        if cached_property and not _is_ghost_record(cached_property):
                            # FIX: Check if cache has the wrong city (legacy "Houston" for non-Harris)
                            cached_addr = cached_property.get('address', '')
                            if current_district and current_district != "HCAD" and "Houston" in cached_addr and district_city not in cached_addr:
                                 logger.info(f"Correcting cached address city for {current_district}: {cached_addr}")
                                 cached_property['address'] = cached_addr.replace("Houston, TX", district_city)
                            property_details = cached_property
                        else:
                            # Scraper returned nothing — rely on the early property type to decide what to do
                            lookup_addr = original_address or account_number
                            
                            is_confirmed_residential = ptype == "Residential"

                            # SOFT GATE: Always attempt API enrichment regardless of propertyType.
                            # Only hard-fail if enrichment also comes back empty AND type is confirmed residential.
                            yield json.dumps({"status": "🏢 Commercial Enrichment: Querying RealEstateAPI + RentCast for fallback data..."}) + "\n"
                            enriched = await commercial_agent.enrich_property(lookup_addr)
                            if enriched and (enriched.get('appraised_value', 0) > 0 or enriched.get('building_area', 0) > 0):
                                property_details = {
                                    "account_number": current_account,
                                    "district": current_district or "HCAD",
                                    "property_type": "commercial",
                                    **enriched
                                }
                                logger.info(f"Commercial enrichment fallback succeeded: appraised=${property_details.get('appraised_value',0):,.0f}, area={property_details.get('building_area',0)} sqft")
                            elif is_confirmed_residential:
                                # Enrichment failed AND confirmed residential — genuine miss
                                logger.error(f"Confirmed Residential miss for account {current_account} — district scraper returned nothing and enrichment failed.")
                                yield json.dumps({"error": f"Could not retrieve property details for account '{current_account}' from the appraisal district portal. Please verify the account number or use the Manual Override fields to enter values directly."}) + "\n"
                                return
                            else:
                                logger.error(f"Commercial enrichment returned no usable data for '{lookup_addr}'.")
                                yield json.dumps({"error": f"Could not retrieve property data for '{lookup_addr}'. This appears to be a commercial or non-standard property not accessible via public appraisal records or our API partners. Try the Manual Override fields to enter values directly."}) + "\n"
                                return
            
            # AGGRESSIVE CLEANING
            raw_addr = property_details.get('address', '')
            district_context = property_details.get('district', 'HCAD')
            cleaned_addr = normalize_address(raw_addr, district_context)
            if raw_addr != cleaned_addr:
                property_details['address'] = cleaned_addr

            if manual_address: property_details['address'] = manual_address
            if manual_value: property_details['appraised_value'] = manual_value
            if manual_area: property_details['building_area'] = manual_area

            # POST-LOAD GHOST CHECK: if property_details has placeholder/zero values
            # (scraper returned a stub OR DB ghost slipped through), trigger commercial enrichment.
            if _is_ghost_record(property_details) and not manual_value:
                lookup_addr = (
                    property_details.get('address')
                    or original_address
                    or account_number
                )
                
                is_confirmed_residential = ptype == "Residential"

                if not is_confirmed_residential:
                    yield json.dumps({"status": "🏢 Commercial Enrichment: Fetching real data from RealEstateAPI + RentCast..."}) + "\n"
                    enriched = await commercial_agent.enrich_property(lookup_addr)
                    if enriched and (enriched.get('appraised_value', 0) > 0 or enriched.get('building_area', 0) > 0):
                        property_details = {
                            **property_details,       # keep account_number, district, etc.
                            **enriched,               # overwrite with real values
                            "property_type": "commercial",
                        }
                        logger.info(f"Post-load enrichment OK: appraised=${property_details.get('appraised_value',0):,.0f}, area={property_details.get('building_area',0)} sqft")
                    else:
                        logger.warning(f"Post-load commercial enrichment returned no data for '{lookup_addr}'.")
                        # Don't abort — continue with whatever we have (manual override might save it)

            # Update cache
            if property_details and is_real_address(property_details.get('address')):
                try:
                    clean_prop = {
                        "account_number": property_details.get("account_number"),
                        "address": property_details.get("address"),
                        "appraised_value": property_details.get("appraised_value"),
                        "building_area": property_details.get("building_area"),
                        "year_built": property_details.get("year_built"),
                        "neighborhood_code": property_details.get("neighborhood_code"),
                        "district": property_details.get("district")
                    }
                    await supabase_service.upsert_property(clean_prop)
                except: pass

            # Enrich property_details with owner/legal info from API sources
            # (HCAD scraping is inconsistent for these fields)
            if property_details and rentcast_fallback_data:
                rc = rentcast_fallback_data.get('rentcast_data', {}) or {}
                enrich_fields = {
                    'owner_name': rc.get('ownerName') or rc.get('owner') or rentcast_fallback_data.get('owner_name'),
                    'mailing_address': rc.get('mailingAddress') or rc.get('ownerMailingAddress') or rentcast_fallback_data.get('mailing_address'),
                    'legal_description': rc.get('legalDescription') or rentcast_fallback_data.get('legal_description'),
                    'land_area': rc.get('lotSize') or rentcast_fallback_data.get('land_area'),
                }
                for k, v in enrich_fields.items():
                    if v and not property_details.get(k):
                        property_details[k] = v
                        logger.info(f"Enriched property_details['{k}'] from RentCast/API fallback")

            yield json.dumps({"status": "📊 Market Analyst: Querying RentCast for market values..."}) + "\n"
            
            # 3. Market Data
            market_value = property_details.get('appraised_value', 0)
            prop_address = property_details.get('address', '')
            
            if is_real_address(prop_address):
                try:
                    market_data = None
                    if rentcast_fallback_data:
                        rc_data = rentcast_fallback_data.get('rentcast_data', {})
                        market_data = {
                            'sale_price': rc_data.get('lastSalePrice'),
                            'sale_date': rc_data.get('lastSaleDate'),
                            'source': 'RentCast (Cached)'
                        }
                    if not market_data:
                        market_data = await bridge.get_last_sale_price(prop_address)

                    if market_data and market_data.get('sale_price') is not None:
                        market_value = market_data['sale_price']
                    
                    if not market_value or market_value == 0:
                        market_value = await bridge.get_estimated_market_value(
                            property_details.get('appraised_value', 0), prop_address
                        )
                except:
                    if not market_value or market_value == 0:
                        market_value = property_details.get('appraised_value', 0)
            
            # 3b. Permit Analysis (Subject Property)
            subject_permits = []
            if is_real_address(prop_address):
                subject_permits = await permit_agent.get_property_permits(prop_address)
            permit_summary = permit_agent.analyze_permits(subject_permits)
            property_details['permit_summary'] = permit_summary

            # 4. Sales Comparison Analysis (Independent of Equity)
            print("DEBUG: Executing Sales Analysis Block in Main...")
            yield json.dumps({"status": "💰 Sales Agent: Fetching recent sales comparables..."}) + "\n"
            logger.info("Main: Calling get_sales_analysis...")
            try:
                sales_results = equity_engine.get_sales_analysis(property_details)
                print(f"DEBUG: get_sales_analysis result type: {type(sales_results)}")
            except Exception as e:
                print(f"DEBUG: get_sales_analysis CRASHED: {e}")
                sales_results = None
                
            equity_results = {} # Initialize early
            if sales_results:
                count = sales_results.get('sales_count', 0)
                logger.info(f"Main: get_sales_analysis returned {count} comps.")
                equity_results['sales_comps'] = sales_results.get('sales_comps', [])
                equity_results['sales_count'] = count
            else:
                logger.warning("Main: get_sales_analysis returned None.")

            yield json.dumps({"status": "⚖️ Equity Specialist: Discovering comparable properties..."}) + "\n"

            # 4. Equity Analysis — DB-first for ALL districts
            try:
                prop_address = property_details.get('address', 'Houston, TX')
                nbhd_code = property_details.get('neighborhood_code')
                bld_area  = int(property_details.get('building_area') or 0)
                prop_district = property_details.get('district', current_district or 'HCAD')
                real_neighborhood = []

                # Layer 0: DB lookup by neighborhood_code + building_area (no browser needed)
                if nbhd_code and bld_area > 0:
                    db_comps = await supabase_service.get_neighbors_from_db(
                        current_account, nbhd_code, bld_area, district=prop_district
                    )
                    if len(db_comps) >= 3:
                        real_neighborhood = db_comps
                        yield json.dumps({"status": f"⚖️ Equity Specialist: Found {len(real_neighborhood)} comps from database instantly."}) + "\n"

                # Layer 1: Cached comps (previously scraped)
                if not real_neighborhood:
                    cached_comps = await supabase_service.get_cached_comps(current_account)
                    if cached_comps:
                        real_neighborhood = cached_comps
                        yield json.dumps({"status": f"⚖️ Equity Specialist: Using {len(real_neighborhood)} cached comps."}) + "\n"

                async def scrape_pool(pool_list, limit=3):
                    sem = asyncio.Semaphore(limit)
                    async def safe_scrape(neighbor):
                        async with sem:
                            return await connector.get_property_details(neighbor['account_number'])
                    logger.info(f"Deep-scraping pool of {len(pool_list[:10])} neighbors...")
                    tasks = [safe_scrape(n) for n in pool_list[:10]]
                    deep_results = await asyncio.gather(*tasks)
                    usable = []
                    for res in deep_results:
                        if res and res.get('building_area', 0) > 0:
                            usable.append(res)
                            try:
                                await supabase_service.upsert_property({
                                    "account_number": res.get("account_number"),
                                    "address": res.get("address"),
                                    "appraised_value": res.get("appraised_value"),
                                    "building_area": res.get("building_area"),
                                    "year_built": res.get("year_built")
                                })
                            except: pass
                    return usable

                # Layers 2-3: Playwright fallback (cloud may be blocked)
                if not real_neighborhood:
                    yield json.dumps({"status": "⚖️ Equity Specialist: DB insufficient — scraping live neighbors..."}) + "\n"
                    street_only = prop_address.split(",")[0].strip()
                    addr_parts = street_only.split()
                    street_name = " ".join(addr_parts[1:]) if addr_parts and addr_parts[0][0].isdigit() else " ".join(addr_parts)

                    # Street search
                    discovered_neighbors = await connector.get_neighbors_by_street(street_name)
                    if discovered_neighbors:
                        discovered_neighbors = [n for n in discovered_neighbors if n['account_number'] != property_details.get('account_number')]
                        real_neighborhood = await scrape_pool(discovered_neighbors)

                # Neighborhood code scrape fallback
                if not real_neighborhood:
                    if nbhd_code and nbhd_code != "Unknown":
                        logger.info(f"No usable neighbors on street. Trying Nbhd Code fallback: {nbhd_code}")
                        yield json.dumps({"status": f"⚖️ Equity Specialist: Expanding to neighborhood {nbhd_code}..."}) + "\n"
                        nbhd_neighbors = await connector.get_neighbors(nbhd_code)
                        if nbhd_neighbors:
                            # Filter out subject
                            nbhd_neighbors = [n for n in nbhd_neighbors if n['account_number'] != property_details.get('account_number')]
                            real_neighborhood = await scrape_pool(nbhd_neighbors)
                
                logger.info(f"Final discovery pool size: {len(real_neighborhood)}")
                
                # Fallback if discovery completely fails — for commercial, use sales comps as equity pool
                if not real_neighborhood:
                    if str(property_details.get('property_type', '')).lower() == 'commercial':
                        logger.info("Commercial property: no district neighbors found. Building equity pool from sales comps...")
                        yield json.dumps({"status": "🏢 Commercial Equity: Building value pool from recent sales comparables..."}) + "\n"
                        real_neighborhood = commercial_agent.get_equity_comp_pool(
                            property_details.get('address', account_number), property_details
                        )
                        if real_neighborhood:
                            equity_results['note'] = (
                                "Equity analysis is based on recent sales comparables "
                                "(commercial property — no district neighbor records available)."
                            )
                            logger.info(f"Commercial equity pool: {len(real_neighborhood)} comps available.")
                        else:
                            # No comps either — skip equity, continue to vision/narrative
                            logger.warning("Commercial equity pool empty. Skipping equity analysis.")
                            equity_results['error'] = "No comparable sales found for equity analysis."
                    else:
                        friendly_error = "Could not find sufficient data for equity analysis. Please try again later or verify the address."
                        logger.warning("Live discovery found no usable neighbors. Returning error to user.")
                        yield json.dumps({"error": friendly_error}) + "\n"
                        return # Stop execution gracefully

                equity_results['justified_value_floor'] = equity_engine.find_equity_5(property_details, real_neighborhood).get('justified_value_floor', 0)
                # Merge full equity results safely
                eq_full = equity_engine.find_equity_5(property_details, real_neighborhood)
                equity_results.update(eq_full)
                
                # 4b. Comparative Permit Analysis
                comp_renovations = await permit_agent.summarize_comp_renovations(equity_results.get('equity_5', []))
                property_details['comp_renovations'] = comp_renovations
            except Exception as e:
                logger.error(f"Equity Analysis Error: {e}")
                # Don't clobber sales comps in equity_results if they exist
                if "sales_comps" not in equity_results:
                    equity_results["error"] = "Could not perform live equity analysis"

            # ── 4c. Anomaly Detection: Score subject against neighborhood ─────
            try:
                nbhd_for_anomaly = property_details.get('neighborhood_code')
                dist_for_anomaly = property_details.get('district', current_district or 'HCAD')
                if nbhd_for_anomaly:
                    yield json.dumps({"status": "📊 Anomaly Detector: Scoring property against neighborhood..."}) + "\n"
                    anomaly_score = await anomaly_agent.score_property(
                        current_account, nbhd_for_anomaly, dist_for_anomaly
                    )
                    if anomaly_score and not anomaly_score.get('error'):
                        equity_results['anomaly_score'] = anomaly_score
                        property_details['anomaly_score'] = anomaly_score
                        z = anomaly_score.get('z_score', 0)
                        pctile = anomaly_score.get('percentile', 0)
                        logger.info(f"AnomalyDetector: Subject Z={z}, percentile={pctile}")
                        if z > 1.5:
                            yield json.dumps({"status": f"📊 Anomaly Detected: Property is at the {pctile:.0f}th percentile in its neighborhood (Z={z:.1f})"}) + "\n"
            except Exception as e:
                logger.warning(f"Anomaly detection failed (non-fatal): {e}")

            # ── 4d. Geo-Intelligence: Distance + External Obsolescence ────────
            try:
                from backend.services.geo_intelligence_service import (
                    enrich_comps_with_distance, check_external_obsolescence, geocode
                )
                prop_address_geo = property_details.get('address', '')
                if equity_results.get('equity_5') and prop_address_geo:
                    yield json.dumps({"status": "🌐 Geo-Intelligence: Computing distances and checking surroundings..."}) + "\n"
                    subj_coords = geocode(prop_address_geo)
                    enrich_comps_with_distance(prop_address_geo, equity_results['equity_5'], subj_coords)
                    # External obsolescence check
                    if subj_coords:
                        obs_result = check_external_obsolescence(subj_coords['lat'], subj_coords['lng'])
                        if obs_result.get('factors'):
                            equity_results['external_obsolescence'] = obs_result
                            property_details['external_obsolescence'] = obs_result
                            yield json.dumps({"status": f"🌐 Geo-Intelligence: Found {len(obs_result['factors'])} external obsolescence factor(s)"}) + "\n"
            except Exception as geo_err:
                logger.warning(f"Geo-intelligence failed (non-fatal): {geo_err}")

            # 5. Vision & Location Analysis (Flood Zones)
            search_address = property_details.get('address', '')
            district_key = property_details.get('district', 'HCAD')
            known_cities = ["Houston, TX", "Austin, TX", "Dallas, TX", "Plano, TX", "Fort Worth, TX"]
            
            # Smart Append: Only append city if none of the known major cities are present
            if not any(city in search_address for city in known_cities):
                 d_map = {
                    "HCAD": ", Houston, TX",
                    "TCAD": ", Austin, TX",
                    "DCAD": ", Dallas, TX",
                    "CCAD": ", Plano, TX",
                    "TAD": ", Fort Worth, TX"
                 }
                 suffix = d_map.get(district_key, ", Houston, TX")
                 search_address += suffix
            
            # Geocode once for both Vision and FEMA
            coords = vision_agent._geocode_address(search_address)
            
            # FEMA Check
            flood_data = None
            if coords:
                flood_data = await fema_agent.get_flood_zone(coords['lat'], coords['lng'])
                if flood_data:
                    property_details['flood_zone'] = flood_data.get('zone', 'Zone X')
            
            # Vision Analysis
            yield json.dumps({"status": "📸 Vision Agent: Analyzing property condition..."}) + "\n"
            # Use the cleaned search_address for vision acquisition
            image_paths = await vision_agent.get_street_view_images(search_address)
            
            # Check Vision Cache first (the agent also checks, but we log it here if it's instant)
            cached_vision = await supabase_service.get_cached_vision(current_account)
            if cached_vision:
                yield json.dumps({"status": "📸 Vision Agent: Using cached property condition analysis..."}) + "\n"
            
            vision_detections = await vision_agent.analyze_property_condition(image_paths, property_details)
            
            yield json.dumps({"status": "🔍 AI Condition Analyst: Comparing property conditions across comps..."}) + "\n"
            
            # Combine external obsolescence from FEMA into narrative context
            if flood_data and flood_data.get('is_high_risk'):
                fema_arg = fema_agent.get_deduction_argument(flood_data)
                if fema_arg:
                    vision_detections.append({
                        "issue": fema_arg['factor'],
                        "description": fema_arg['argument'],
                        "severity": fema_arg['impact'],
                        "deduction": 0,
                        "confidence": 1.0,
                        "type": "location"
                    })
            
            # Combine Permit data for narrative
            if not permit_summary.get('has_renovations'):
                vision_detections.append({
                    "issue": "No Recent Improvements",
                    "description": "City of Houston permit records indicate no major renovations or improvements in the last 10+ years, supporting a 'deferred maintenance' model for valuation.",
                    "severity": "Low",
                    "deduction": 0,
                    "confidence": 0.9,
                    "type": "permit"
                })
            
            # Use annotated image if possible for evidence
            image_path = image_paths[0] if image_paths else "mock_street_view.jpg"
            if vision_detections and image_path != "mock_street_view.jpg":
                image_path = vision_agent.draw_detections(image_path, vision_detections)

            # ── 5b. Condition Delta: Compare subject vs comp conditions ────────
            try:
                from backend.services.condition_delta_service import enrich_comps_with_condition
                if equity_results.get('equity_5') and image_path != "mock_street_view.jpg":
                    yield json.dumps({"status": "📸 Condition Delta: Comparing property condition against comps..."}) + "\n"
                    # Pass vision detections for subject score extraction
                    property_details['vision_detections'] = vision_detections
                    delta_result = await enrich_comps_with_condition(
                        property_details, equity_results['equity_5'],
                        vision_agent, subject_image_path=image_path
                    )
                    if delta_result:
                        equity_results['condition_delta'] = delta_result
                        delta_val = delta_result.get('condition_delta', 0)
                        if delta_val < -1:
                            yield json.dumps({"status": f"📸 Condition Delta: Subject is in worse condition than comps (Δ={delta_val:.1f})"}) + "\n"
            except Exception as cd_err:
                logger.warning(f"Condition delta failed (non-fatal): {cd_err}")

            yield json.dumps({"status": "\u2728 Savings Estimator: Computing predicted savings range..."}) + "\n"

            # 5c. Predictive Savings Estimation
            try:
                from backend.services.savings_estimator import SavingsEstimator
                estimator = SavingsEstimator(tax_rate=0.025)
                savings_prediction = estimator.estimate(property_details, equity_results)
                equity_results['savings_prediction'] = savings_prediction
                if savings_prediction.get('signal_count', 0) > 0:
                    prob = savings_prediction.get('protest_success_probability', 0)
                    exp_save = savings_prediction['estimated_savings']['expected']
                    yield json.dumps({"status": f"\u2728 Protest Strength: {savings_prediction['protest_strength']} ({prob:.0%}) — Expected savings: ${exp_save:,}/yr"}) + "\n"
            except Exception as se_err:
                logger.warning(f"Savings estimator failed (non-fatal): {se_err}")

            yield json.dumps({"status": "✍️ Legal Narrator: Evaluating protest viability..."}) + "\n"
            
            # 6. Narrative & PDF
            narrative = narrative_agent.generate_protest_narrative(property_details, equity_results, vision_detections, market_value)
            
            yield json.dumps({"status": f"✍️ Legal Narrator: Generating protest narrative ({equity_results.get('sales_count', 0)} sales comps support reduction)..."}) + "\n"
            
            os.makedirs("outputs", exist_ok=True)
            form_path = f"outputs/Form_41_44_{current_account}.pdf"
            form_service.generate_form_41_44(property_details, {
                "narrative": narrative, 
                "vision_data": vision_detections, 
                "evidence_image_path": image_path,
                "equity_results": equity_results
            }, form_path)

            # Final Save
            try:
                prop_record = await supabase_service.get_property_by_account(current_account)
                if prop_record and "justified_value_floor" in equity_results:
                    # Use savings estimator if available, else simple formula
                    sp = equity_results.get('savings_prediction', {})
                    potential_savings = sp.get('estimated_savings', {}).get('expected', 0) if sp else 0
                    if not potential_savings:
                        potential_savings = (property_details.get('appraised_value', 0) - equity_results['justified_value_floor']) * 0.025
                    protest_record = {
                        "property_id": prop_record['id'],
                        "justified_value": equity_results['justified_value_floor'],
                        "potential_savings": potential_savings,
                        "narrative": narrative,
                        "pdf_url": form_path
                    }
                    saved_protest = await supabase_service.save_protest(protest_record)
                    
                    if saved_protest:
                        logger.info(f"✅ Saved protest record ID: {saved_protest.get('id')}")
                        
                        # Save the comps used for this protest
                        # real_neighborhood contains the final used comps (whether neighbors or sales)
                        if real_neighborhood:
                            try:
                                logger.info(f"Saving {len(real_neighborhood)} equity comps to DB...")
                                # Sanitize comps to remove _raw fields that cause Supabase insert errors
                                clean_comps = []
                                for c in real_neighborhood:
                                    # Create a clean copy with only primitive types + no large blobs
                                    clean = {
                                        k: v for k, v in c.items() 
                                        if k not in ('_raw', 'raw', 'geometry', 'similarity_rationale') 
                                        and not isinstance(v, (dict, list)) # flat structure only
                                    }
                                    # Ensure essential fields are present
                                    if 'account_number' in clean:
                                        clean_comps.append(clean)
                                
                                await supabase_service.save_equity_comps(saved_protest['id'], clean_comps) 
                                logger.info(f"✅ Saved {len(clean_comps)} equity comps.")
                            except Exception as e:
                                logger.error(f"Failed to save equity comps: {e}")
                    else:
                        logger.warning("Failed to save protest record (no ID returned).")

            except Exception as e:
                logger.error(f"❌ DB Save Failed: {e}")

            # Final Payload
            yield json.dumps({"data": {
                "property": property_details,
                "market_value": market_value,
                "equity": equity_results,
                "vision": vision_detections,
                "narrative": narrative,
                "form_path": form_path,
                "evidence_image_path": image_path
            }}) + "\n"

        except Exception as e:
            error_msg = str(e)
            friendly_detail = error_msg
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                friendly_detail = "API Rate Limit Hit: Too many requests. Please wait a minute and try again."
            logger.error(f"FATAL ERROR: {error_msg}\n{traceback.format_exc()}")
            yield json.dumps({"error": friendly_detail}) + "\n"

    return StreamingResponse(protest_generator(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    # Final safety check before uvicorn starts
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Disable reload on Windows if using Playwright to avoid loop conflicts
    use_reload = sys.platform != 'win32'
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=use_reload)
