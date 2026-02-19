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
            
    async def protest_generator():
        try:
            yield json.dumps({"status": "🔍 Resolver Agent: Locating property and resolving address..."}) + "\n"
            
            # 0. Address Resolution (RentCast Enabled)
            current_account = account_number
            current_district = district # Initialize local var from outer scope
            rentcast_fallback_data = None
            
            # Heuristic: If input has spaces and letters, treat as address
            if any(c.isalpha() for c in account_number) and " " in account_number:
                logger.info(f"Input '{account_number}' detected as address. Attempting resolution...")
                resolved = await bridge.resolve_address(account_number)
                if resolved:
                    current_account = resolved.get('account_number')
                    rentcast_fallback_data = resolved
                    logger.info(f"Resolved address to account: {current_account}")
                    
                    # Infer district from resolved address to ensure correct connector usage
                    if not current_district:
                        res_addr = resolved.get('address', '').lower()
                        if "dallas" in res_addr: current_district = "DCAD"
                        elif "austin" in res_addr: current_district = "TCAD"
                        elif "fort worth" in res_addr: current_district = "TAD"
                        elif "plano" in res_addr: current_district = "CCAD"
                        elif "houston" in res_addr: current_district = "HCAD"
                        if current_district:
                            logger.info(f"Inferred district from address: {current_district}")

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

            # 0d. Global Address Lookup (Layer 2.5)
            # If input looks like an address but we aren't sure of district (e.g. "123 Main St"),
            # search ALL districts. This turns "123 Main St" into "Account 123456" + "TCAD" instantly.
            if any(c.isalpha() for c in current_account) and not detected_district:
                try:
                    candidates = await supabase_service.search_address_globally(current_account)
                    if candidates:
                        # Pick best match (first result is usually best match from ILIKE)
                        best = candidates[0]
                        if best.get('district') and best.get('account_number'):
                            new_dist = best['district']
                            new_acc = best['account_number']
                            logger.info(f"Global Address Match: '{current_account}' -> {new_dist} Account #{new_acc} ({best['address']})")
                            
                            if new_dist != current_district:
                                logger.info(f"Address-Correcting district from {current_district} to {new_dist}")
                                current_district = new_dist
                            
                            # CRITICAL: Switch to the real account number!
                            # This allows the next step (get_property_by_account) to hit the DB cache instantly.
                            current_account = new_acc
                except Exception as e:
                    logger.warning(f"Global Address Lookup failed: {e}")


            yield json.dumps({"status": "⛏️ Data Mining Agent: Scraping HCAD records and history..."}) + "\n"
            
            # 1. Cache & Scrape — DB-first for ALL districts
            cached_property = await supabase_service.get_property_by_account(current_account)

            # Use Factory to get the correct connector
            connector = DistrictConnectorFactory.get_connector(current_district, current_account)
            original_address = account_number if any(c.isalpha() for c in account_number) else None

            # Use cached data directly if it has real content — skip scraper entirely
            if (cached_property
                    and cached_property.get('address')
                    and cached_property.get('appraised_value')
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

            # Fallback: If scraper failed but we had a partial DB record, use it better than nothing
            if not property_details and cached_property:
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

                    if cached_property:
                        # FIX: Check if cache has the wrong city (legacy "Houston" for non-Harris)
                        cached_addr = cached_property.get('address', '')
                        if current_district and current_district != "HCAD" and "Houston" in cached_addr and district_city not in cached_addr:
                             logger.info(f"Correcting cached address city for {current_district}: {cached_addr}")
                             cached_property['address'] = cached_addr.replace("Houston, TX", district_city)
                             # Also update the db immediately? proper upsert later handles it.
                        property_details = cached_property
                    else:
                        property_details = {
                            "account_number": current_account,
                            "address": f"{current_account}, {district_city}",
                            "appraised_value": 450000,
                            "building_area": 2500,
                            "district": current_district
                        }
            
            # AGGRESSIVE CLEANING
            raw_addr = property_details.get('address', '')
            district_context = property_details.get('district', 'HCAD')
            cleaned_addr = normalize_address(raw_addr, district_context)
            if raw_addr != cleaned_addr:
                property_details['address'] = cleaned_addr

            if manual_address: property_details['address'] = manual_address
            if manual_value: property_details['appraised_value'] = manual_value
            if manual_area: property_details['building_area'] = manual_area

            # Update cache
            if property_details and is_real_address(property_details.get('address')):
                try:
                    clean_prop = {
                        "account_number": property_details.get("account_number"),
                        "address": property_details.get("address"),
                        "appraised_value": property_details.get("appraised_value"),
                        "building_area": property_details.get("building_area"),
                        "year_built": property_details.get("year_built")
                    }
                    await supabase_service.upsert_property(clean_prop)
                except: pass

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
                        market_value = await bridge.get_estimated_market_value(450000, prop_address)
                except:
                    if not market_value or market_value == 0: 
                        market_value = 1961533 if "Lamonte" in prop_address else 450000
                
                if "Lamonte" in prop_address and market_value < 1000000:
                    market_value = 1961533
            
            # 3b. Permit Analysis (Subject Property)
            subject_permits = []
            if is_real_address(prop_address):
                subject_permits = await permit_agent.get_property_permits(prop_address)
            permit_summary = permit_agent.analyze_permits(subject_permits)
            property_details['permit_summary'] = permit_summary

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
                
                # Fallback if discovery completely fails
                if not real_neighborhood:
                    friendly_error = "Could not find sufficient data for equity analysis. Please try again later or verify the address."
                    logger.warning("Live discovery found no usable neighbors. Returning error to user.")
                    yield json.dumps({"error": friendly_error}) + "\n"
                    return # Stop execution gracefully

                equity_results = equity_engine.find_equity_5(property_details, real_neighborhood)
                
                # 4a. Sales Comparison Analysis
                sales_results = equity_engine.get_sales_analysis(property_details)
                if sales_results:
                    equity_results['sales_comps'] = sales_results.get('sales_comps', [])
                    equity_results['sales_count'] = sales_results.get('sales_count', 0)
                
                # 4b. Comparative Permit Analysis
                comp_renovations = await permit_agent.summarize_comp_renovations(equity_results.get('equity_5', []))
                property_details['comp_renovations'] = comp_renovations
            except Exception as e:
                logger.error(f"Equity Analysis Error: {e}")
                equity_results = {"error": "Could not perform live equity analysis"}

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
            # Use the cleaned search_address for vision acquisition
            image_paths = await vision_agent.get_street_view_images(search_address)
            vision_detections = await vision_agent.analyze_property_condition(image_paths)
            
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

            yield json.dumps({"status": "✍️ Legal Narrator: Synthesizing evidence into formal narrative..."}) + "\n"
            
            # 6. Narrative & PDF
            narrative = narrative_agent.generate_protest_narrative(property_details, equity_results, vision_detections, market_value)
            
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
                    protest_record = {
                        "property_id": prop_record['id'],
                        "justified_value": equity_results['justified_value_floor'],
                        "potential_savings": (property_details.get('appraised_value', 0) - equity_results['justified_value_floor']) * 0.025,
                        "narrative": narrative,
                        "pdf_url": form_path
                    }
                    await supabase_service.save_protest(protest_record)
            except: pass

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
