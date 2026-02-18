import streamlit as st
import os
import sys

# MUST be at the very top: Add project root to sys.path so 'backend' is discoverable
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pandas as pd
import json
import asyncio
import logging
from PIL import Image
from dotenv import load_dotenv

# MUST be set before any subprocess/playwright calls on Windows
if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except:
        pass

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import Agents directly
from backend.agents.district_factory import DistrictConnectorFactory
from backend.agents.non_disclosure_bridge import NonDisclosureBridge
from backend.agents.equity_agent import EquityAgent
from backend.agents.vision_agent import VisionAgent
from backend.services.narrative_pdf_service import NarrativeAgent, PDFService
from backend.db.supabase_client import supabase_service
from backend.services.hcad_form_service import HCADFormService
from backend.agents.fema_agent import FEMAAgent
from backend.agents.permit_agent import PermitAgent
from backend.utils.address_utils import normalize_address, is_real_address

st.set_page_config(page_title="Texas Equity AI", layout="wide")

# Initialize Agents (Cached for performance)
@st.cache_resource
def setup_playwright():
    """Install Playwright browsers if missing (Required for Streamlit Cloud)"""
    if sys.platform != "win32":
        try:
            import subprocess
            logger.info("Installing Playwright Chromium...")
            # Only install the browser binary, NOT the system deps (handled by packages.txt)
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            logger.info("Playwright Chromium installed successfully.")
        except Exception as e:
            logger.error(f"Failed to install Playwright: {e}")

@st.cache_resource
def get_agents():
    # Ensure browsers are installed before agents start
    setup_playwright()
    return {

        "factory": DistrictConnectorFactory(),
        "bridge": NonDisclosureBridge(),
        "equity_engine": EquityAgent(),
        "vision_agent": VisionAgent(),
        "narrative_agent": NarrativeAgent(),
        "pdf_service": PDFService(),
        "form_service": HCADFormService(),
        "fema_agent": FEMAAgent(),
        "permit_agent": PermitAgent()
    }

agents = get_agents()

# Custom CSS for polished look
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Auto-Detection Logic
if "district_selector" not in st.session_state:
    st.session_state.district_selector = "HCAD"

def auto_detect_district():
    if "account_input" not in st.session_state:
        return
    raw_acc = st.session_state.account_input
    if not raw_acc:
        return
    clean_acc = raw_acc.replace("-", "").replace(" ", "").strip()
    target_district = None
    if len(clean_acc) == 17: target_district = "DCAD"
    elif len(clean_acc) == 13 and clean_acc.isdigit(): target_district = "HCAD"
    elif raw_acc.upper().strip().startswith("R"): target_district = "CCAD"
    elif len(clean_acc) <= 7 and clean_acc.isdigit(): target_district = "TCAD"
    elif len(clean_acc) == 8 and clean_acc.isdigit(): target_district = "TAD"
    elif any(c.isalpha() for c in raw_acc):
        lower_acc = raw_acc.lower()
        if "dallas" in lower_acc: target_district = "DCAD"
        elif "austin" in lower_acc: target_district = "TCAD"
        elif "fort worth" in lower_acc: target_district = "TAD"
        elif "plano" in lower_acc: target_district = "CCAD"
        elif "houston" in lower_acc: target_district = "HCAD"
    if target_district and target_district != st.session_state.district_selector:
        st.session_state.district_selector = target_district
        st.toast(f"📍 Auto-switched District to **{target_district}**", icon="🔄")

auto_detect_district()

# Sidebar
st.sidebar.title("Texas Equity AI 🤠")
st.sidebar.markdown("Automating property tax protests in Texas.")

district_options = ("HCAD", "TAD", "CCAD", "DCAD", "TCAD")

district_code = st.sidebar.selectbox(
    "Appraisal District",
    district_options,
    key="district_selector",
    help="Select the county appraisal district."
)

with st.sidebar.expander("Manual Data (Optional Override)"):
    m_address = st.text_input("Property Address")
    m_value = st.number_input("Appraised Value", value=0)
    m_area = st.number_input("Building Area (sqft)", value=0)

st.sidebar.divider()
st.sidebar.subheader("📈 Savings Calculator")
tax_rate = st.sidebar.slider("Property Tax Rate (%)", 1.0, 4.0, 2.5, 0.1)

# Main Content
st.title("Property Tax Protest Dashboard")

account_placeholder = "e.g. 0660460360030"
if district_code == "TAD": account_placeholder = "e.g. 00002345678"
elif district_code == "CCAD": account_placeholder = "e.g. R-1234-567-890"

account_number = st.text_input(f"Enter {district_code} Account Number or Street Address", 
                              placeholder=account_placeholder,
                              key="account_input")

async def protest_generator_local(account_number, manual_address=None, manual_value=None, manual_area=None, district=None):
    try:
        yield {"status": "🔍 Resolver Agent: Locating property and resolving address..."}
        current_account = account_number
        current_district = district
        rentcast_fallback_data = None
        if any(c.isalpha() for c in account_number) and " " in account_number:
            resolved = await agents["bridge"].resolve_address(account_number)
            if resolved:
                current_account = resolved.get('account_number')
                rentcast_fallback_data = resolved
                if not current_district:
                    res_addr = resolved.get('address', '').lower()
                    if "dallas" in res_addr: current_district = "DCAD"
                    elif "austin" in res_addr: current_district = "TCAD"
                    elif "fort worth" in res_addr: current_district = "TAD"
                    elif "plano" in res_addr: current_district = "CCAD"
                    elif "houston" in res_addr: current_district = "HCAD"
        detected_district = DistrictConnectorFactory.detect_district_from_account(current_account)
        if detected_district and detected_district != current_district:
            current_district = detected_district
        yield {"status": f"⛏️ Data Mining Agent: Scraping {current_district or 'District'} records..."}
        cached_property = await supabase_service.get_property_by_account(current_account)
        connector = DistrictConnectorFactory.get_connector(current_district, current_account)
        original_address = account_number if any(c.isalpha() for c in account_number) else None
        property_details = await connector.get_property_details(current_account, address=original_address)
        if property_details and property_details.get('account_number'):
            current_account = property_details.get('account_number')
        if not property_details:
             property_details = cached_property or {
                "account_number": current_account,
                "address": f"{current_account}, Texas",
                "appraised_value": manual_value or 450000,
                "building_area": manual_area or 2500,
                "district": current_district
            }
        raw_addr = property_details.get('address', '')
        district_context = property_details.get('district', 'HCAD')
        property_details['address'] = normalize_address(raw_addr, district_context)
        if manual_address: property_details['address'] = manual_address
        if manual_value: property_details['appraised_value'] = manual_value
        if manual_area: property_details['building_area'] = manual_area
        yield {"status": "📊 Market Analyst: Querying RentCast for market values..."}
        market_value = property_details.get('appraised_value', 0)
        prop_address = property_details.get('address', '')
        if is_real_address(prop_address):
            try:
                market_data = await agents["bridge"].get_last_sale_price(prop_address)
                if market_data and market_data.get('sale_price'):
                    market_value = market_data['sale_price']
                if not market_value:
                    market_value = await agents["bridge"].get_estimated_market_value(property_details.get('appraised_value', 450000), prop_address)
            except: pass
        subject_permits = await agents["permit_agent"].get_property_permits(prop_address)
        permit_summary = agents["permit_agent"].analyze_permits(subject_permits)
        property_details['permit_summary'] = permit_summary
        yield {"status": "⚖️ Equity Specialist: Discovering live neighbors..."}
        try:
            street_only = prop_address.split(",")[0].strip()
            addr_parts = street_only.split()
            # Skip house number for discovery
            street_name = " ".join(addr_parts[1:]) if addr_parts and addr_parts[0][0].isdigit() else " ".join(addr_parts)
            
            # Semi-parallel scraping helper with concurrency limit
            async def scrape_pool(pool_list, limit=3):
                usable = []
                sem = asyncio.Semaphore(limit)
                
                async def safe_scrape(neighbor):
                    async with sem:
                        return await connector.get_property_details(neighbor['account_number'])
                
                tasks = [safe_scrape(n) for n in pool_list[:10]]
                deep_results = await asyncio.gather(*tasks)
                return [res for res in deep_results if res and res.get('building_area', 0) > 0]

            # Layer 1: Street-level search
            discovered_neighbors = await connector.get_neighbors_by_street(street_name)
            real_neighborhood = []
            if discovered_neighbors:
                # Filter out subject property
                discovered_neighbors = [n for n in discovered_neighbors if n['account_number'] != property_details.get('account_number')]
                real_neighborhood = await scrape_pool(discovered_neighbors)
                
            # Layer 2: Neighborhood code fallback (only for residential codes)
            if not real_neighborhood:
                nbhd_code = property_details.get('neighborhood_code')
                is_commercial = connector.is_commercial_neighborhood_code(nbhd_code) if nbhd_code else False
                
                if is_commercial:
                    logger.info(f"Neighborhood code '{nbhd_code}' is commercial — skipping neighborhood-wide search.")
                    yield {"error": f"⚠️ This appears to be a **commercial property** (Neighborhood Code: '{nbhd_code}'). Residential equity analysis requires comparable residential properties. Please verify the property type and try a manual address override if needed."}
                    return
                elif nbhd_code and nbhd_code != "Unknown":
                    logger.info(f"Street search yielded 0 usable comps. Trying neighborhood code '{nbhd_code}'...")
                    nbhd_neighbors = await connector.get_neighbors(nbhd_code)
                    if nbhd_neighbors:
                        # Filter out subject property
                        nbhd_neighbors = [n for n in nbhd_neighbors if n['account_number'] != property_details.get('account_number')]
                        real_neighborhood = await scrape_pool(nbhd_neighbors)
                        
            if not real_neighborhood:
                yield {"error": "Could not find sufficient comparable properties for equity analysis. The property may be unique, commercial, or in a low-density area. Try using a manual address override."}
                return

            equity_results = agents["equity_engine"].find_equity_5(property_details, real_neighborhood)
            property_details['comp_renovations'] = await agents["permit_agent"].summarize_comp_renovations(equity_results.get('equity_5', []))
        except Exception as e:
            equity_results = {"error": str(e)}
        yield {"status": "📸 Vision Agent: Analyzing property condition..."}
        search_address = property_details.get('address', '')
        coords = agents["vision_agent"]._geocode_address(search_address)
        if coords:
            flood_data = await agents["fema_agent"].get_flood_zone(coords['lat'], coords['lng'])
            if flood_data: property_details['flood_zone'] = flood_data.get('zone', 'Zone X')
        image_paths = await agents["vision_agent"].get_street_view_images(search_address)
        vision_detections = await agents["vision_agent"].analyze_property_condition(image_paths)
        image_path = image_paths[0] if image_paths else "mock_street_view.jpg"
        if vision_detections and image_path != "mock_street_view.jpg":
            image_path = agents["vision_agent"].draw_detections(image_path, vision_detections)
        yield {"status": "✍️ Legal Narrator: Finalizing protest packet..."}
        narrative = agents["narrative_agent"].generate_protest_narrative(property_details, equity_results, vision_detections, market_value)
        os.makedirs("outputs", exist_ok=True)
        form_path = f"outputs/Form_41_44_{current_account}.pdf"
        agents["form_service"].generate_form_41_44(property_details, {
            "narrative": narrative, 
            "vision_data": vision_detections, 
            "evidence_image_path": image_path,
            "equity_results": equity_results
        }, form_path)
        yield {"data": {
            "property": property_details, "market_value": market_value, "equity": equity_results,
            "vision": vision_detections, "narrative": narrative, "form_path": form_path, "evidence_image_path": image_path
        }}
    except Exception as e: yield {"error": str(e)}

if st.button("🚀 Generate Protest Packet", type="primary"):
    if not account_number:
        st.error("Please enter an account number or address.")
    else:
        with st.status("🏗️ Building your Protest Packet...", expanded=True) as status:
            final_data = None
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            async def main_loop():
                data = None
                async for chunk in protest_generator_local(
                    account_number, manual_address=m_address or None,
                    manual_value=m_value if m_value > 0 else None,
                    manual_area=m_area if m_area > 0 else None, district=district_code
                ):
                    if "status" in chunk: st.write(chunk["status"])
                    if "error" in chunk:
                        st.error(chunk["error"])
                        status.update(label="❌ Generation Failed", state="error", expanded=True)
                        return None
                    if "data" in chunk:
                        data = chunk["data"]
                return data

            final_data = loop.run_until_complete(main_loop())
            if final_data:
                status.update(label="✅ Protest Packet Ready!", state="complete", expanded=False)
                data = final_data
                tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 Property", "⚖️ Equity", "📸 Vision", "📄 Protest", "⚙️ Data"])
                with tab1:
                    col1, col2 = st.columns(2)
                    with col1: st.subheader("Details"); st.json(data['property'])
                    with col2:
                        st.subheader("Market Analysis")
                        appraised = data['property'].get('appraised_value', 0)
                        market = data['market_value']
                        st.metric("Appraised Value", f"${appraised:,.0f}")
                        st.metric("Market Value", f"${market:,.0f}", delta=f"${market - appraised:,.0f}", delta_color="inverse")
                with tab2:
                    st.subheader("Equity Analysis")
                    if "error" in data['equity'] or not data['equity']: st.error("Equity analysis failed.")
                    else:
                        justified_val = data['equity'].get('justified_value_floor', 0)
                        savings = max(0, appraised - justified_val)
                        c1, c2 = st.columns(2)
                        with c1: st.metric("Justified Value", f"${justified_val:,.0f}", delta=f"-${savings:,.0f}" if savings > 0 else None)
                        with c2: st.metric("💰 Est. Savings", f"${savings * (tax_rate/100):,.0f}")
                        st.dataframe(pd.DataFrame(data['equity'].get('equity_5', [])))
                with tab3:
                    st.subheader("Condition")
                    if os.path.exists(data.get('evidence_image_path', '')): st.image(data['evidence_image_path'], width=600)
                    st.write(data.get('vision', []))
                with tab4:
                    st.subheader("Narrative"); st.info(data['narrative'])
                    if os.path.exists(data.get('form_path', '')):
                        with open(data['form_path'], "rb") as f:
                            st.download_button("⬇️ Download PDF", f, file_name="protest.pdf", mime="application/pdf")
                with tab5: st.json(data)
