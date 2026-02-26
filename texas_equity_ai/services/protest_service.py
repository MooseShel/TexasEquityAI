"""
Protest generation pipeline — extracted from frontend/app.py lines 840–1667.

This is a clean async generator that yields status updates and final data.
It is called by AppState.generate_protest() in state.py.
All backend agent imports are identical to the Streamlit version.
"""
import os
import sys
import asyncio
import logging
import re
import traceback
from typing import Optional, AsyncGenerator

# Ensure project root on path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"), override=False)

from backend.agents.district_factory import DistrictConnectorFactory
from backend.agents.non_disclosure_bridge import NonDisclosureBridge
from backend.agents.equity_agent import EquityAgent
from backend.agents.vision_agent import VisionAgent
from backend.agents.sales_agent import SalesAgent
from backend.services.narrative_pdf_service import NarrativeAgent, PDFService
from backend.db.supabase_client import supabase_service
from backend.services.hcad_form_service import HCADFormService
from backend.agents.fema_agent import FEMAAgent
from backend.agents.permit_agent import PermitAgent
from backend.agents.crime_agent import CrimeAgent
from backend.utils.address_utils import normalize_address, is_real_address
from backend.agents.anomaly_detector import AnomalyDetectorAgent
import shutil
import reflex as rx

logger = logging.getLogger(__name__)


def _get_upload_dir() -> str:
    """Get the Reflex upload directory (writable at runtime, served by backend)."""
    try:
        upload_dir = str(rx.get_upload_dir())
    except Exception:
        upload_dir = os.path.join(project_root, "uploaded_files")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _copy_to_upload(src_path: str) -> str:
    """Copy a local file into the Reflex upload dir and return the basename."""
    if not src_path or not os.path.isfile(src_path):
        return ""
    upload_dir = _get_upload_dir()
    basename = os.path.basename(src_path)
    dest = os.path.join(upload_dir, basename)
    if not os.path.exists(dest):
        try:
            shutil.copy2(src_path, dest)
        except Exception as e:
            logger.warning(f"Failed to copy {src_path} to upload dir: {e}")
            return ""
    return basename  # return just the filename, state will use rx.get_upload_url()

# ── Agent singletons ───────────────────────────────────────────────
_agents = None

def _get_agents():
    global _agents
    if _agents is None:
        _agents = {
            "factory": DistrictConnectorFactory(),
            "bridge": NonDisclosureBridge(),
            "equity_engine": EquityAgent(),
            "vision_agent": VisionAgent(),
            "sales_agent": SalesAgent(),
            "narrative_agent": NarrativeAgent(),
            "pdf_service": PDFService(),
            "form_service": HCADFormService(),
            "fema_agent": FEMAAgent(),
            "permit_agent": PermitAgent(),
            "crime_agent": CrimeAgent(),
            "anomaly_agent": AnomalyDetectorAgent(),
        }
    return _agents


async def run_protest_pipeline(
    account_number: str,
    district: str = "HCAD",
    manual_address: Optional[str] = None,
    manual_value: Optional[float] = None,
    manual_area: Optional[float] = None,
    force_fresh_comps: bool = False,
    tax_rate: float = 2.5,
) -> AsyncGenerator[dict, None]:
    """
    Async generator that mirrors the original protest_generator_local().
    Yields dicts with keys: 'status', 'warning', 'error', or 'data'.
    """
    agents = _get_agents()
    equity_results = {}

    try:
        yield {"status": "🔍 Resolver Agent: Locating property and resolving address..."}
        current_account = account_number
        current_district = district
        rentcast_fallback_data = None

        is_address_input = any(c.isalpha() for c in account_number) and " " in account_number
        if is_address_input:
            resolved = await agents["bridge"].resolve_account_id(account_number, district)
            if resolved:
                current_account = resolved["account_number"]
                current_district = resolved.get("district") or current_district
                rentcast_fallback_data = resolved.get("rentcast_data")
                source = resolved.get("source", "?")
                conf = resolved.get("confidence", 1.0)
                yield {"status": f"✅ Resolver [{source}]: Found account ID {current_account} (confidence {conf:.0%})"}
                logger.info(f"ID resolved via {source}: {account_number!r} → {current_account}")
            else:
                from backend.utils.address_utils import normalize_address_for_search
                normalized_input = normalize_address_for_search(account_number)
                if normalized_input and normalized_input != account_number:
                    current_account = normalized_input
                    logger.info(f"Resolver: no ID found, using normalized address for scraper: '{normalized_input}'")

        detected_district = DistrictConnectorFactory.detect_district_from_account(current_account)
        if detected_district and detected_district != current_district:
            current_district = detected_district

        if not is_address_input:
            try:
                db_record = await supabase_service.get_property_by_account(current_account)
                if db_record and db_record.get('district'):
                    db_dist = db_record.get('district')
                    if current_district and db_dist != current_district:
                        current_district = db_dist
            except Exception:
                pass

        yield {"status": f"⛏️ Data Mining Agent: Scraping {current_district or 'District'} records..."}
        cached_property = await supabase_service.get_property_by_account(current_account)

        if not cached_property and any(c.isalpha() for c in current_account):
            try:
                street_part = current_account.split(",")[0].strip()
                addr_candidates = await supabase_service.search_address_globally(street_part, limit=3)
                if addr_candidates:
                    best = addr_candidates[0]
                    real_acct = best.get('account_number')
                    if real_acct:
                        logger.info(f"Address fallback: '{current_account}' → {real_acct}")
                        current_account = real_acct
                        current_district = best.get('district') or current_district
                        cached_property = await supabase_service.get_property_by_account(current_account)
            except Exception as e:
                logger.warning(f"Address fallback failed: {e}")

        connector = DistrictConnectorFactory.get_connector(current_district, current_account)
        original_address = account_number if any(c.isalpha() for c in account_number) else None

        def is_valid_cache(rec):
            if not rec:
                return False
            has_real_value = rec.get('appraised_value') and rec.get('appraised_value') not in (450000, 0)
            has_real_area = rec.get('building_area') and rec.get('building_area') != 2500
            has_year = bool(rec.get('year_built'))
            has_nbhd = bool(rec.get('neighborhood_code'))
            return has_real_value or has_year or has_nbhd or has_real_area

        # Property type detection
        from backend.agents.property_type_resolver import resolve_property_type
        ptype = "Unknown"
        ptype_source = "Unknown"
        is_likely_commercial = False
        try:
            resolve_addr = original_address or (current_account if any(c.isalpha() for c in current_account) else "")
            ptype, ptype_source = await resolve_property_type(
                account_number=current_account, address=resolve_addr,
                district=current_district or "HCAD",
            )
            is_likely_commercial = (ptype == "Commercial")
            logger.info(f"PropertyTypeResolver: {ptype} ({ptype_source})")
        except Exception as pt_err:
            logger.warning(f"Property type resolution failed: {pt_err}")

        if (is_valid_cache(cached_property) and cached_property.get('address')
                and not manual_value and not manual_address):
            logger.info(f"Using Supabase cached record for {current_account}")
            property_details = cached_property
        else:
            if cached_property and not is_valid_cache(cached_property):
                logger.warning(f"Ghost record for {current_account} — forcing scrape")

            if rentcast_fallback_data:
                rc_ptype = (rentcast_fallback_data.get('rentcast_data') or {}).get('propertyType', '')
                if rc_ptype and rc_ptype not in ('Single Family', 'Condo', 'Townhouse', 'Manufactured', 'Multi-Family'):
                    is_likely_commercial = True
                    ptype_source = f"RentCast_Cached({rc_ptype})"
                elif rc_ptype:
                    ptype_source = f"RentCast_Cached({rc_ptype})"

            if not rentcast_fallback_data or ptype_source == "Unknown":
                yield {"status": "🏢 Property Type Check: Resolving via multi-source chain..."}
                ptype2, src2 = await resolve_property_type(
                    account_number=current_account,
                    address=current_account if any(c.isalpha() for c in current_account) else "",
                    district=current_district or "HCAD",
                )
                ptype, ptype_source = ptype2, src2
                is_likely_commercial = (ptype2 == "Commercial")

            commercial_data = None
            if is_likely_commercial:
                from backend.agents.commercial_enrichment_agent import CommercialEnrichmentAgent
                yield {"status": f"🏢 Commercial Property Detected ({ptype_source}): Prioritizing commercial data sources..."}
                commercial_agent = CommercialEnrichmentAgent()
                enrich_addr = original_address or current_account
                commercial_data = await commercial_agent.enrich_property(enrich_addr)

            if commercial_data and (commercial_data.get('appraised_value', 0) > 0 or commercial_data.get('building_area', 0) > 0):
                property_details = {
                    "account_number": commercial_data.get('account_number') or current_account,
                    "district": current_district or "HCAD",
                    "property_type": "commercial",
                    **commercial_data,
                }
            else:
                if is_likely_commercial:
                    yield {"status": "⚠️ Commercial enrichment yielded limited data. Trying district portal..."}
                else:
                    yield {"status": f"⛏️ Residential Flow: Scraping {current_district or 'District'} records..."}
                property_details = await connector.get_property_details(current_account, address=original_address)

        if property_details and property_details.get('account_number'):
            current_account = property_details.get('account_number')

        if not property_details:
            if rentcast_fallback_data:
                property_details = rentcast_fallback_data
            else:
                yield {"error": f"Could not retrieve property data for '{current_account}'. Please try the Manual Override fields."}
                return

        if ptype != "Unknown" and 'property_type' not in property_details:
            property_details['property_type'] = ptype.lower()
        if ptype_source != "Unknown" and 'ptype_source' not in property_details:
            property_details['ptype_source'] = ptype_source

        # Enrich from RentCast
        if rentcast_fallback_data and isinstance(rentcast_fallback_data, dict):
            rc = rentcast_fallback_data.get('rentcast_data') or rentcast_fallback_data
            for key, val in {'year_built': rc.get('yearBuilt'), 'bedrooms': rc.get('bedrooms'),
                             'bathrooms': rc.get('bathrooms'), 'land_area': rc.get('lotSize')}.items():
                if val and not property_details.get(key):
                    property_details[key] = val

        raw_addr = property_details.get('address', '')
        district_context = property_details.get('district', 'HCAD')
        property_details['address'] = normalize_address(raw_addr, district_context)
        if manual_address:
            property_details['address'] = manual_address
        if manual_value:
            property_details['appraised_value'] = manual_value
        if manual_area:
            property_details['building_area'] = manual_area

        # Cache to Supabase
        if is_real_address(property_details.get('address', '')):
            try:
                clean_prop = {k: property_details.get(k) for k in
                              ["account_number", "address", "appraised_value", "market_value",
                               "building_area", "year_built", "neighborhood_code", "district"]}
                clean_prop = {k: v for k, v in clean_prop.items() if v is not None}
                await supabase_service.upsert_property(clean_prop)
            except Exception as e:
                logger.warning(f"Supabase cache write failed: {e}")

        # Market value resolution
        SUSPICIOUS_VALUES = {999999, 9999999, 99999}
        db_market = float(property_details.get('market_value', 0) or 0)
        appraised_for_market = float(property_details.get('appraised_value', 0) or 0)

        if db_market > 0 and int(db_market) not in SUSPICIOUS_VALUES:
            market_value = db_market
        else:
            market_value = appraised_for_market
            prop_address = property_details.get('address', '')
            if is_real_address(prop_address):
                cached_market = await supabase_service.get_cached_market(current_account)
                if cached_market:
                    cached_val = cached_market.get('market_value', 0)
                    if cached_val and int(cached_val) not in SUSPICIOUS_VALUES:
                        market_value = cached_val
                else:
                    try:
                        market_data = await agents["bridge"].get_last_sale_price(prop_address, resolved_data=rentcast_fallback_data)
                        if market_data and market_data.get('sale_price'):
                            sp = market_data['sale_price']
                            if int(sp) not in SUSPICIOUS_VALUES:
                                market_value = sp
                        if market_value == appraised_for_market:
                            avm = await agents["bridge"].get_estimated_market_value(appraised_for_market, prop_address)
                            if avm and int(avm) not in SUSPICIOUS_VALUES:
                                market_value = avm
                        await supabase_service.save_cached_market(current_account, {'market_value': market_value})
                    except Exception:
                        pass

        # Permits
        prop_address = property_details.get('address', '')
        subject_permits = await agents["permit_agent"].get_property_permits(prop_address)
        permit_summary = agents["permit_agent"].analyze_permits(subject_permits)
        property_details['permit_summary'] = permit_summary

        # ── Equity analysis ─────────────────────────────────────────
        yield {"status": "⚖️ Equity Specialist: Discovering comparable properties..."}
        try:
            if not is_real_address(prop_address):
                yield {"error": f"⚠️ Could not resolve address (got: '{prop_address}'). Try Manual Override."}
                return

            real_neighborhood = []
            nbhd_code = property_details.get('neighborhood_code')
            bld_area = int(property_details.get('building_area') or 0)
            prop_district = property_details.get('district', 'HCAD')

            def _detect_commercial(prop: dict) -> bool:
                pt = str(prop.get('property_type', '') or '').lower().strip()
                COMMERCIAL_KEYWORDS = {'commercial','office','retail','industrial','mixed_use','mixed use','land','vacant','warehouse','restaurant','store','hotel','motel','bank','service','manufacturing','flex','apartment'}
                if any(kw in pt for kw in COMMERCIAL_KEYWORDS):
                    return True
                COMMERCIAL_CODE_PREFIXES = ('F','G','H','J','K','L','X')
                m = re.match(r'^([A-Z])\d?$', pt.upper())
                if m and m.group(1) in COMMERCIAL_CODE_PREFIXES:
                    return True
                sc = str(prop.get('state_class', '') or '').strip().upper()
                if sc and sc[0:1] in COMMERCIAL_CODE_PREFIXES:
                    return True
                return False

            is_commercial_prop = _detect_commercial(property_details) or ptype == "Commercial"
            if is_commercial_prop and not property_details.get('property_type'):
                property_details['property_type'] = 'commercial'

            # Commercial comp discovery
            if is_commercial_prop:
                if nbhd_code:
                    db_comps = await supabase_service.get_neighbors_from_db(current_account, nbhd_code, bld_area, district=prop_district)
                    if len(db_comps) >= 3:
                        real_neighborhood = db_comps
                        yield {"status": f"⚖️ Equity Specialist: Found {len(real_neighborhood)} commercial comps from database."}
                if not real_neighborhood:
                    cached = await supabase_service.get_cached_comps(current_account)
                    if cached:
                        real_neighborhood = cached
                if not real_neighborhood:
                    try:
                        from backend.agents.commercial_enrichment_agent import CommercialEnrichmentAgent
                        ca = CommercialEnrichmentAgent()
                        yield {"status": "🏢 Commercial Equity: Building value pool from sales comparables..."}
                        pool = await asyncio.to_thread(ca.get_equity_comp_pool, property_details.get('address', account_number), property_details)
                        if pool:
                            real_neighborhood = pool
                    except Exception as ce:
                        logger.error(f"Commercial comp pool error: {ce}")

            # Residential (or fallback)
            if not real_neighborhood:
                if not force_fresh_comps and nbhd_code and bld_area > 0:
                    db_comps = await supabase_service.get_neighbors_from_db(current_account, nbhd_code, bld_area, district=prop_district)
                    if len(db_comps) >= 3:
                        real_neighborhood = db_comps
                        yield {"status": f"⚖️ Equity Specialist: Found {len(real_neighborhood)} comps from database."}
                if not real_neighborhood and not force_fresh_comps:
                    cached = await supabase_service.get_cached_comps(current_account)
                    if cached:
                        real_neighborhood = cached

            # Playwright scraping (residential only)
            if not real_neighborhood and not is_commercial_prop:
                yield {"status": "⚖️ Equity Specialist: DB insufficient — scraping live neighbors..."}
                street_only = prop_address.split(",")[0].strip()
                addr_parts = street_only.split()
                if addr_parts and addr_parts[0][0:1].isdigit():
                    addr_parts = addr_parts[1:]
                KNOWN_CITIES = {"HOUSTON","DALLAS","AUSTIN","FORT","WORTH","PLANO","ARLINGTON","IRVING","GARLAND","FRISCO","MCKINNEY","SUGAR","LAND","KATY","SPRING","HUMBLE","PEARLAND","PASADENA","BAYTOWN","LEAGUE","CITY","GALVESTON"}
                while addr_parts:
                    last = addr_parts[-1].upper().rstrip(".,")
                    if (last.isdigit() and len(last) == 5) or (last.isalpha() and len(last) == 2 and last.isupper()) or last in KNOWN_CITIES:
                        addr_parts.pop()
                    else:
                        break
                street_name = " ".join(addr_parts)

                async def scrape_pool(pool_list, limit=3):
                    sem = asyncio.Semaphore(limit)
                    async def safe_scrape(neighbor):
                        async with sem:
                            return await connector.get_property_details(neighbor['account_number'])
                    tasks = [safe_scrape(n) for n in pool_list[:10]]
                    results = await asyncio.gather(*tasks)
                    return [r for r in results if r and (r.get('building_area', 0) > 0 or r.get('appraised_value', 0) > 0)]

                discovered = await connector.get_neighbors_by_street(street_name)
                if discovered:
                    discovered = [n for n in discovered if n['account_number'] != property_details.get('account_number')]
                    real_neighborhood = await scrape_pool(discovered)

                if not real_neighborhood and nbhd_code and nbhd_code != "Unknown":
                    nbhd_neighbors = await connector.get_neighbors(nbhd_code)
                    if nbhd_neighbors:
                        nbhd_neighbors = [n for n in nbhd_neighbors if n['account_number'] != property_details.get('account_number')]
                        real_neighborhood = await scrape_pool(nbhd_neighbors)

                if real_neighborhood:
                    try:
                        await supabase_service.save_cached_comps(current_account, real_neighborhood)
                    except Exception:
                        pass

            # Final API fallback
            if not real_neighborhood:
                try:
                    from backend.agents.commercial_enrichment_agent import CommercialEnrichmentAgent
                    yield {"status": "🏢 Fallback Comps: Querying API sales comps..."}
                    ca_fallback = CommercialEnrichmentAgent()
                    pool_fb = await asyncio.to_thread(ca_fallback.get_equity_comp_pool, property_details.get('address', account_number), property_details)
                    if pool_fb:
                        real_neighborhood = pool_fb
                except Exception:
                    pass

            if not real_neighborhood:
                yield {"error": "Could not find sufficient comparable properties. Try manual address override."}
                return

            equity_results = await asyncio.to_thread(agents["equity_engine"].find_equity_5, property_details, real_neighborhood)

            # Sales comps
            try:
                cached_sales = await supabase_service.get_cached_sales(current_account)
                if cached_sales:
                    yield {"status": "💰 Sales Specialist: Using cached sales comparables..."}
                    equity_results['sales_comps'] = cached_sales
                    equity_results['sales_count'] = len(cached_sales)
                else:
                    yield {"status": "💰 Sales Specialist: Searching for recent comparable sales..."}
                    sales_results = await asyncio.to_thread(agents["equity_engine"].get_sales_analysis, property_details)
                    if sales_results:
                        equity_results['sales_comps'] = sales_results.get('sales_comps', [])
                        equity_results['sales_count'] = sales_results.get('sales_count', 0)
                        raw_sales = sales_results.get('sales_comps', [])
                        serializable = []
                        for sc in raw_sales:
                            if hasattr(sc, '__dict__'):
                                serializable.append({k: v for k, v in sc.__dict__.items() if not k.startswith('_')})
                            elif isinstance(sc, dict):
                                serializable.append(sc)
                        if serializable:
                            await supabase_service.save_cached_sales(current_account, serializable)
            except Exception as e:
                logger.error(f"Sales error: {e}")

            property_details['comp_renovations'] = await agents["permit_agent"].summarize_comp_renovations(equity_results.get('equity_5', []))

            # Anomaly detection
            try:
                nbhd_for_anomaly = property_details.get('neighborhood_code')
                dist_for_anomaly = property_details.get('district', 'HCAD')
                if nbhd_for_anomaly:
                    yield {"status": "📊 Anomaly Detector: Scoring property against neighborhood..."}
                    anomaly_score = await agents["anomaly_agent"].score_property(current_account, nbhd_for_anomaly, dist_for_anomaly)
                    if anomaly_score and not anomaly_score.get('error'):
                        equity_results['anomaly_score'] = anomaly_score
                        property_details['anomaly_score'] = anomaly_score
                        z = anomaly_score.get('z_score', 0)
                        pctile = anomaly_score.get('percentile', 0)
                        if z > 1.5:
                            yield {"status": f"🚨 Anomaly Detected: {pctile:.0f}th percentile (Z={z:.1f})"}
            except Exception:
                pass

            # Geo-intelligence
            try:
                from backend.services.geo_intelligence_service import enrich_comps_with_distance, check_external_obsolescence, geocode
                equity_comps_geo = equity_results.get('equity_5', [])
                if equity_comps_geo and prop_address:
                    yield {"status": "🌐 Geo-Intelligence: Computing distances..."}
                    subj_coords = await asyncio.to_thread(geocode, prop_address)
                    await asyncio.to_thread(enrich_comps_with_distance, prop_address, equity_comps_geo, subj_coords)
                    if subj_coords:
                        obs_result = await asyncio.to_thread(check_external_obsolescence, subj_coords['lat'], subj_coords['lng'])
                        if obs_result.get('factors'):
                            equity_results['external_obsolescence'] = obs_result
                            property_details['external_obsolescence'] = obs_result
            except Exception:
                pass

            # Crime analysis
            try:
                crime_address = property_details.get('address', '')
                detected_d = property_details.get('district', prop_district or 'HCAD')
                if crime_address and is_real_address(crime_address) and detected_d in ('HCAD',):
                    yield {"status": "🚨 Intelligence Agent: Checking neighborhood crime..."}
                    crime_stats = await agents["crime_agent"].get_local_crime_data(crime_address)
                    if crime_stats and crime_stats.get('count', 0) > 0:
                        obs = property_details.get('external_obsolescence', {'factors': []})
                        if 'factors' not in obs:
                            obs['factors'] = []
                        severity_impact = 5.0 if crime_stats['count'] > 15 else (2.5 if crime_stats['count'] > 5 else 1.0)
                        crime_factor = {"description": crime_stats.get('message', ''), "impact_pct": severity_impact}
                        obs['factors'].append(crime_factor)
                        property_details['external_obsolescence'] = obs
                        if 'external_obsolescence' not in equity_results:
                            equity_results['external_obsolescence'] = {'factors': []}
                        if 'factors' not in equity_results['external_obsolescence']:
                            equity_results['external_obsolescence']['factors'] = []
                        equity_results['external_obsolescence']['factors'].append(crime_factor)
                        yield {"status": f"🚨 Intelligence Agent: Elevated crime risk (+{severity_impact}% obsolescence)"}
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Equity analysis failed: {e}\n{traceback.format_exc()}")
            equity_results = {"error": str(e)}

        # ── Vision analysis ─────────────────────────────────────────
        yield {"status": "📸 Vision Agent: Analyzing property condition..."}
        search_address = property_details.get('address', '')
        flood_data = None
        coords = await asyncio.to_thread(agents["vision_agent"]._geocode_address, search_address)
        if coords:
            cached_flood = await supabase_service.get_cached_flood(current_account)
            if cached_flood:
                flood_data = cached_flood
            else:
                flood_data = await agents["fema_agent"].get_flood_zone(coords['lat'], coords['lng'])
                if flood_data:
                    await supabase_service.save_cached_flood(current_account, flood_data)
            if flood_data:
                property_details['flood_zone'] = flood_data.get('zone', 'Zone X')

        cached_vision = await supabase_service.get_cached_vision(current_account)
        if cached_vision and cached_vision.get('detections') is not None:
            yield {"status": "📸 Vision Agent: Using cached property condition analysis..."}
            vision_detections = cached_vision.get('detections')
            image_paths = cached_vision.get('image_paths', [])
            missing = [p for p in image_paths if p and not os.path.exists(p) and p != "mock_street_view.jpg"]
            if missing and search_address:
                yield {"status": "📸 Vision Agent: Restoring Street View images..."}
                image_paths = await agents["vision_agent"].get_street_view_images(search_address)
                try:
                    await supabase_service.save_cached_vision(current_account, {'detections': vision_detections, 'image_paths': image_paths})
                except Exception:
                    pass
        else:
            image_paths = await agents["vision_agent"].get_street_view_images(search_address)
            vision_detections = await agents["vision_agent"].analyze_property_condition(image_paths, property_details)
            try:
                await supabase_service.save_cached_vision(current_account, {'detections': vision_detections, 'image_paths': image_paths})
            except Exception:
                pass

        image_path = image_paths[0] if image_paths else "mock_street_view.jpg"
        annotated_paths = []
        if vision_detections:
            for ip in image_paths:
                if ip and ip != "mock_street_view.jpg":
                    annotated = agents["vision_agent"].draw_detections(ip, vision_detections)
                    annotated_paths.append(annotated)
        if not annotated_paths:
            annotated_paths = image_paths if image_paths else []
        if annotated_paths:
            image_path = annotated_paths[0]

        # Condition delta
        comp_images = {}
        try:
            from backend.services.condition_delta_service import enrich_comps_with_condition
            equity_comps_cd = equity_results.get('equity_5', []) if isinstance(equity_results, dict) else []
            if equity_comps_cd and image_path and image_path != "mock_street_view.jpg":
                yield {"status": "📸 AI Condition Analyst: Analyzing conditions in parallel..."}
                comp_images['subject'] = image_path
                property_details['vision_detections'] = vision_detections
                delta_result = await asyncio.wait_for(
                    enrich_comps_with_condition(property_details, equity_comps_cd, agents["vision_agent"], subject_image_path=image_path),
                    timeout=15,
                )
                if delta_result:
                    equity_results['condition_delta'] = delta_result
                    score_labels = {10:'Excellent',8:'Very Good',7:'Good',6:'Average',5:'Fair',4:'Below Average',3:'Poor',2:'Very Poor',1:'Condemned'}
                    subj_score = delta_result.get('subject_condition_score', 6)
                    comp_images['subject_condition'] = score_labels.get(subj_score, 'Average')
                    for cc in delta_result.get('comp_conditions', []):
                        addr = cc.get('address')
                        if addr and cc.get('image_path'):
                            comp_images[addr] = cc['image_path']
                            comp_images[f"{addr}_condition"] = cc.get('summary', '')
        except asyncio.TimeoutError:
            logger.warning("Condition delta timed out after 15s — continuing without condition analysis")
            yield {"status": "⚠️ Condition analysis timed out — continuing..."}
        except Exception:
            pass

        # Savings estimation
        try:
            from backend.services.savings_estimator import SavingsEstimator
            estimator = SavingsEstimator(tax_rate=tax_rate / 100)
            savings_prediction = estimator.estimate(property_details, equity_results)
            if isinstance(equity_results, dict):
                equity_results['savings_prediction'] = savings_prediction
        except Exception:
            pass

        # ML prediction
        try:
            from backend.services.protest_predictor import predict_protest_success
            ml_prediction = predict_protest_success(property_details, equity_results)
            if isinstance(equity_results, dict):
                equity_results['ml_prediction'] = ml_prediction
            win_pct = ml_prediction.get('win_probability_pct', '?%')
            yield {"status": f"🎯 AI Win Predictor: {win_pct} probability"}
        except Exception:
            pass

        # ── Narrative generation ────────────────────────────────────
        yield {"status": "✍️ Legal Narrator: Evaluating protest viability..."}

        def _safe_flt(v):
            if not v:
                return 0.0
            if isinstance(v, (int, float)):
                return float(v)
            try:
                return float(str(v).replace('$', '').replace(',', '').strip())
            except Exception:
                return 0.0

        appraised_val = _safe_flt(property_details.get('appraised_value', 0))
        justified_val = _safe_flt(equity_results.get('justified_value_floor', 0) if isinstance(equity_results, dict) else 0)
        mv = _safe_flt(market_value)

        has_equity = justified_val > 0 and appraised_val > justified_val
        has_market = mv > 0 and appraised_val > mv
        has_condition = bool(vision_detections and len(vision_detections) > 0)
        flood_zone = property_details.get('flood_zone', 'Zone X')
        has_flood = flood_zone and 'Zone X' not in flood_zone

        has_sales = False
        sales_comps_v = equity_results.get('sales_comps', []) if isinstance(equity_results, dict) else []
        if sales_comps_v:
            try:
                prices = [float(str(c.get('Sale Price', '0')).replace('$', '').replace(',', '')) for c in sales_comps_v]
                prices = [p for p in prices if p > 0]
                if prices:
                    prices.sort()
                    median = prices[len(prices) // 2]
                    has_sales = appraised_val > median
            except Exception:
                pass

        protest_viable = has_equity or has_market or has_condition or has_flood or has_sales

        if protest_viable:
            yield {"status": "✍️ Legal Narrator: Generating protest narrative..."}
            try:
                # Wrap sync narrative generation in thread pool to allow timeout
                loop = asyncio.get_event_loop()
                narrative = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, 
                        agents["narrative_agent"].generate_protest_narrative,
                        property_details, equity_results, vision_detections, market_value
                    ),
                    timeout=30
                )
            except asyncio.TimeoutError:
                logger.warning("Narrative generation timed out after 30s")
                narrative = "⚠️ Narrative generation timed out. Please refer to the raw data sections for details."
                yield {"status": "⚠️ Legal Narrator: Timed out — proceeding with raw data..."}
            except Exception as e:
                logger.error(f"Narrative generation failed: {e}")
                narrative = f"⚠️ Narrative generation failed: {str(e)}"
        else:
            narrative = (
                "⚠️ No Protest Recommended Based on Current Data\n\n"
                "The analysis did not find grounds for a property tax protest at this time.\n\n"
                f"• Equity: Justified value (${justified_val:,.0f}) is not lower than appraised (${appraised_val:,.0f}).\n"
                f"• Market: No significant gap detected.\n"
                f"• Condition: No physical issues identified.\n"
                f"• Flood Risk: {flood_zone} (minimal risk).\n\n"
                "If you believe there are grounds not captured here, use Manual Override."
            )

        # ── PDF generation ──────────────────────────────────────────
        upload_dir = _get_upload_dir()
        filename = f"ProtestPacket_{current_account}.pdf"
        combined_path = os.path.join(upload_dir, filename)
        pdf_error = None
        
        yield {"status": "📄 Output Generation: Saving protest packet PDF..."}
        try:
            await asyncio.to_thread(
                agents["pdf_service"].generate_evidence_packet,
                narrative, property_details, equity_results, vision_detections, combined_path,
                sales_data=equity_results.get('sales_comps', []),
                comp_images=comp_images
            )
            yield {"status": "✅ Generation Complete"}
        except Exception as e:
            logger.error(f"PDF generation failed: {traceback.format_exc()}")
            pdf_error = str(e)

        # ── Final yield — deliver results to UI immediately ─────────
        # Image paths: copy to upload dir, return basenames for rx.get_upload_url()
        evidence_basename = _copy_to_upload(image_path) if image_path and image_path != "mock_street_view.jpg" else ""
        image_basenames = [b for b in [_copy_to_upload(v) for v in (comp_images.values() if comp_images else [])] if b]

        yield {
            "status": "✅ Generation complete.",
            "data": {
                "property": property_details,
                "equity": equity_results,
                "vision": vision_detections,
                "narrative": narrative,
                "market_value": market_value,
                "combined_pdf_path": filename if not pdf_error else "",
                "pdf_error": pdf_error,
                "evidence_image_path": evidence_basename,
                "all_image_paths": image_basenames
            }
        }

        # ── Save to DB (best-effort, after results delivered) ─────────
        try:
            protest_record = {
                "account_number": current_account,
                "property_data": property_details,
                "equity_data": equity_results,
                "vision_data": vision_detections,
                "narrative": narrative,
                "market_value": market_value,
                "status": "complete",
            }
            saved = await asyncio.wait_for(supabase_service.save_protest(protest_record), timeout=10)
            if saved and equity_results.get('equity_5'):
                await asyncio.wait_for(supabase_service.save_equity_comps(saved.get('id', current_account), equity_results.get('equity_5')), timeout=10)
            if saved and equity_results.get('sales_comps'):
                await asyncio.wait_for(supabase_service.save_sales_comparables(current_account, saved.get('id', current_account), equity_results.get('sales_comps')), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("DB save timed out after 10s — skipping")
        except Exception as e:
            logger.error(f"DB save failed: {e}")

    except Exception as e:
        yield {"error": str(e)}
