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
import requests
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
from backend.agents.sales_agent import SalesAgent
from backend.services.narrative_pdf_service import NarrativeAgent, PDFService
from backend.db.supabase_client import supabase_service
from backend.services.hcad_form_service import HCADFormService
from backend.agents.fema_agent import FEMAAgent
from backend.agents.permit_agent import PermitAgent
from backend.utils.address_utils import normalize_address, is_real_address
from backend.agents.anomaly_detector import AnomalyDetectorAgent

st.set_page_config(page_title="Texas Equity AI", page_icon="logo.webp", layout="wide")

st.sidebar.image("logo.webp", use_container_width=True)

# ── QR Code / Link Routing (Enhancement #10) ─────────────────────────────────
# Check if the app is loaded with ?account=XXXXXXXX
query_params = st.query_params
url_account = query_params.get("account")

if url_account:
    # ── MOBILE-FIRST REPORT VIEWER ───────────────────────────────────
    # This renders when accessed via QR code: ?account=XXXXXXXX
    st.markdown("""
    <style>
    .report-hero { 
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        color: white; padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem;
    }
    .report-hero h1 { color: white; font-size: 1.5rem; margin: 0; }
    .report-hero p { color: #94a3b8; margin: 0.25rem 0; }
    .metric-card {
        background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
        padding: 1rem; text-align: center;
    }
    .metric-card .value { font-size: 1.5rem; font-weight: 700; color: #1e293b; }
    .metric-card .label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; }
    .badge-strong { background: #22c55e; color: white; padding: 4px 12px; border-radius: 20px; font-weight: 600; }
    .badge-moderate { background: #eab308; color: white; padding: 4px 12px; border-radius: 20px; font-weight: 600; }
    .badge-weak { background: #ef4444; color: white; padding: 4px 12px; border-radius: 20px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Fetch property from DB
        prop = loop.run_until_complete(supabase_service.get_property_by_account(url_account))
        saved_protest = loop.run_until_complete(supabase_service.get_latest_protest(url_account))

        # Quick anomaly check
        anomaly_data = None
        try:
            nbhd = prop.get('neighborhood_code', '') if prop else ''
            if nbhd:
                anomaly_data = loop.run_until_complete(
                    agents["anomaly_agent"].score_property(url_account, nbhd, 'HCAD')
                )
        except Exception:
            pass
        loop.close()

        if not prop:
            st.warning(f"No property found for account {url_account}.")
            st.info("This property may not be in our database yet. Use the main dashboard to generate a protest report first.")
            st.stop()

        address = prop.get('address', f'Account {url_account}')
        appraised = float(prop.get('appraised_value', 0) or 0)
        market = float(prop.get('market_value', 0) or 0)
        area = float(prop.get('building_area', 0) or 0)
        year_built = prop.get('year_built', 'N/A')
        nbhd_code = prop.get('neighborhood_code', 'N/A')

        # ── Hero Card ─────────────────────────────────────────────────
        st.markdown(f"""
        <div class="report-hero">
            <h1>📋 Property Tax Evidence Report</h1>
            <p><strong>{address}</strong></p>
            <p>Account: {url_account} | Neighborhood: {nbhd_code} | Built: {year_built}</p>
        </div>
        """, unsafe_allow_html=True)

        # ── Key Metrics ───────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Appraised Value", f"${appraised:,.0f}")
        c2.metric("Market Value", f"${market:,.0f}")
        c3.metric("Building Area", f"{area:,.0f} ft²")
        pps = appraised / area if area > 0 else 0
        c4.metric("$/ft²", f"${pps:,.0f}")

        # ── Protest Summary ───────────────────────────────────────────
        if saved_protest:
            justified = float(saved_protest.get('justified_value', 0) or 0)
            savings = float(saved_protest.get('potential_savings', 0) or 0)
            reduction = appraised - justified if justified > 0 else 0
            reduction_pct = (reduction / appraised * 100) if appraised > 0 and reduction > 0 else 0

            st.divider()
            st.subheader("💰 Savings Analysis")
            s1, s2, s3 = st.columns(3)
            s1.metric("Justified Value", f"${justified:,.0f}", delta=f"-${reduction:,.0f}", delta_color="inverse")
            s2.metric("Reduction", f"{reduction_pct:.1f}%")
            s3.metric("Est. Tax Savings", f"${savings:,.0f}/yr")

        # ── Anomaly Score ─────────────────────────────────────────────
        if anomaly_data and not anomaly_data.get('error'):
            z = anomaly_data.get('z_score', 0)
            pctile = anomaly_data.get('percentile', 0)
            st.divider()
            st.subheader("📊 Neighborhood Analysis")
            a1, a2, a3 = st.columns(3)
            a1.metric("Z-Score", f"{z:.2f}")
            a2.metric("Percentile", f"{pctile:.0f}th")
            badge_class = "badge-strong" if z > 1.5 else ("badge-moderate" if z > 1.0 else "badge-weak")
            flag = "OVER-ASSESSED" if z > 1.5 else ("ELEVATED" if z > 1.0 else "NORMAL")
            a3.markdown(f'<span class="{badge_class}">{flag}</span>', unsafe_allow_html=True)

            nbhd_stats = anomaly_data.get('neighborhood_stats', {})
            if nbhd_stats:
                st.caption(
                    f"Neighborhood {nbhd_code}: "
                    f"Median $/ft² = ${nbhd_stats.get('median_pps', anomaly_data.get('neighborhood_median_pps', 0)):,.0f} | "
                    f"Your $/ft² = ${pps:,.0f} | "
                    f"Properties analyzed: {nbhd_stats.get('property_count', 'N/A')}"
                )

        # ── Protest Narrative ─────────────────────────────────────────
        if saved_protest and saved_protest.get('narrative'):
            st.divider()
            with st.expander("📜 Full Protest Narrative", expanded=False):
                st.markdown(saved_protest['narrative'])

        # ── Actions ───────────────────────────────────────────────────
        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            st.link_button("🏠 Go to Full Dashboard", f"/?account=")
        with col_b:
            if saved_protest and saved_protest.get('pdf_url'):
                st.info("📄 PDF report available — check your email or the dashboard.")

        st.caption("Generated by Texas Equity AI • texasequityai.streamlit.app")

    except Exception as e:
        st.error(f"Failed to load report: {e}")
        import traceback
        logger.error(f"Report viewer error: {traceback.format_exc()}")

    st.stop()


# ── Live Agent Log Capture ─────────────────────────────────────────────────
class StreamlitLogCapture(logging.Handler):
    """
    Captures backend log messages during protest generation and formats them
    into user-friendly lines that can be shown in a live scrollable panel.
    """
    # Map logger names → (emoji, friendly name)
    AGENT_MAP = {
        "__main__":                                   ("🎯", "Orchestrator"),
        "backend.agents.non_disclosure_bridge":       ("🔗", "Data Bridge"),
        "backend.agents.sales_agent":                 ("💰", "Sales Specialist"),
        "backend.agents.equity_agent":                ("⚖️", "Equity Specialist"),
        "backend.agents.commercial_enrichment_agent": ("🏢", "Commercial Expert"),
        "backend.agents.hcad_scraper":                ("🏛️", "HCAD Scraper"),
        "backend.agents.vision_agent":                ("📸", "Vision Agent"),
        "backend.agents.fema_agent":                  ("🌊", "FEMA Agent"),
        "backend.agents.permit_agent":                ("🔨", "Permit Agent"),
        "backend.agents.rentcast_connector":          ("📊", "RentCast"),
        "backend.agents.realestate_api_connector":    ("🏘️", "RealEstateAPI"),
        "backend.agents.narrative_pdf_service":       ("✍️", "Legal Narrator"),
        "backend.db.supabase_client":                 ("🗄️", "Database"),
    }
    # Noisy loggers to suppress unless they error
    SUPPRESS_INFO = {"httpx", "httpcore", "urllib3", "asyncio"}

    def __init__(self):
        super().__init__()
        self.lines: list = []          # accumulated friendly lines
        self.setLevel(logging.INFO)

    def emit(self, record: logging.LogRecord):
        # Suppress noisy HTTP libraries unless it's a warning/error
        root_name = record.name.split(".")[0]
        if root_name in self.SUPPRESS_INFO and record.levelno < logging.WARNING:
            return

        emoji, name = self.AGENT_MAP.get(
            record.name,
            ("•", record.name.split(".")[-1].replace("_", " ").title())
        )
        # Clean the message: strip the auto-added logger prefix added by basicConfig
        msg = record.getMessage()
        # Truncate very long api payloads
        if len(msg) > 200:
            msg = msg[:197] + "..."

        if record.levelno >= logging.ERROR:
            line = f"❌  {emoji} {name}: {msg}"
        elif record.levelno >= logging.WARNING:
            line = f"⚠️  {emoji} {name}: {msg}"
        else:
            line = f"{emoji} {name}: {msg}"

        self.lines.append(line)

    def flush_display(self, placeholder):
        """Re-render last 60 lines into the placeholder as a styled code block."""
        if self.lines:
            placeholder.code("\n".join(self.lines[-60:]), language=None)

@st.cache_data(show_spinner=False, ttl=3600)
def geocode_address(address: str):
    """Geocode an address using the free Geoapify API.
    Automatically strips unit/suite numbers and retries if the full address fails.
    """
    import re
    if not address or len(address) < 5:
        return None

    def _try_geocode(addr: str):
        try:
            geoapify_key = os.environ.get("GEOAPIFY_API_KEY", "b3a32fdeb3e449a08a474fd3cc89bf2d")
            resp = requests.get(
                "https://api.geoapify.com/v1/geocode/search",
                params={"text": f"{addr}, Texas", "apiKey": geoapify_key, "format": "json"},
            )
            data = resp.json().get('results', [])
            if data:
                return {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}
        except Exception:
            pass
        return None

    # Try full address first
    result = _try_geocode(address)
    if result:
        return result

    # Strip unit/suite suffix (e.g. "# 198", "Suite 4", "Ste B", "Apt 2", "Unit 5") and retry
    cleaned = re.sub(r'\s*(#|Suite|Ste|Apt|Unit)\s*\S+', '', address, flags=re.IGNORECASE).strip().strip(',')
    if cleaned != address:
        result = _try_geocode(cleaned)
        if result:
            return result

    return None


def calc_zoom_level(map_df):
    """Calculate pydeck zoom level to fit all points with padding."""
    import math
    if len(map_df) <= 1:
        return 15
    lat_min, lat_max = map_df["lat"].min(), map_df["lat"].max()
    lon_min, lon_max = map_df["lon"].min(), map_df["lon"].max()
    lat_diff = max(lat_max - lat_min, 0.002)
    lon_diff = max(lon_max - lon_min, 0.002)
    max_diff = max(lat_diff, lon_diff)
    # Approximate: zoom ~= log2(360 / max_diff) - 1, clamped
    zoom = math.log2(360 / max_diff) - 1
    return max(11, min(zoom - 0.5, 16))  # pad slightly, clamp 11-16

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

def get_agents():
    # Ensure browsers are installed before agents start
    setup_playwright()
    return {
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
        "anomaly_agent": AnomalyDetectorAgent(),
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

if "generate_account" in st.query_params:
    st.session_state["account_input"] = st.query_params["generate_account"]
    del st.query_params["generate_account"]

def auto_detect_district():
    if "account_input" not in st.session_state:
        return
    raw_acc = st.session_state.account_input
    if not raw_acc:
        return
    clean_acc = raw_acc.replace("-", "").replace(" ", "").strip()
    target_district = None

    # 1. Account Number Format (Highest Priority)
    if len(clean_acc) == 17: target_district = "DCAD"
    elif len(clean_acc) == 13 and clean_acc.isdigit(): target_district = "HCAD"
    elif raw_acc.upper().strip().startswith("R") and len(clean_acc) <= 10: target_district = "CCAD"
    elif len(clean_acc) == 8 and clean_acc.isdigit(): target_district = "TAD"
    # TCAD 6-7 digits is ambiguous with others, handled by city search below

    # 2. City Name Fallback (Medium Priority)
    if not target_district and any(c.isalpha() for c in raw_acc):
        lower_acc = raw_acc.lower()
        if "dallas" in lower_acc: target_district = "DCAD"
        elif "austin" in lower_acc: target_district = "TCAD"
        elif "fort worth" in lower_acc: target_district = "TAD"
        elif "plano" in lower_acc: target_district = "CCAD"
        elif "houston" in lower_acc: target_district = "HCAD"
        elif "travis" in lower_acc: target_district = "TCAD"
        elif "tarrant" in lower_acc: target_district = "TAD"
        elif "harris" in lower_acc: target_district = "HCAD"

    # 3. ZIP Code Detection (Lowest Priority - Fallback)
    if not target_district:
        zip_map = {
            "750": "CCAD", # Specific override for Plano/Collin area
            "77": "HCAD", "75": "DCAD", "76": "TAD", 
            "787": "TCAD", "786": "TCAD"
        }
        import re
        zip_match = re.search(r'\b(7\d{4})\b', raw_acc)
        if zip_match:
            zip5 = zip_match.group(1)
            for prefix, dist in zip_map.items():
                if zip5.startswith(prefix):
                     target_district = dist
                     break

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

st.sidebar.divider()
st.sidebar.subheader("⚙️ Options")
force_fresh_comps = st.sidebar.checkbox(
    "🔄 Force fresh comps",
    value=False,
    help="Bypass cached comparable properties and re-scrape live data. Use when comps feel outdated (cache TTL: 30 days)."
)

# ── Neighborhood Anomaly Scanner ────────────────────────────────────
st.sidebar.divider()
with st.sidebar.expander("🔍 Neighborhood Anomaly Scan", expanded=False):
    st.caption("Find over-assessed properties in a neighborhood")
    scan_nbhd = st.text_input("Neighborhood Code", placeholder="e.g. 2604.71", key="scan_nbhd_input")
    scan_district = st.selectbox("District", ["HCAD", "TAD", "CCAD", "DCAD", "TCAD"], key="scan_district")
    scan_btn = st.button("📊 Run Scan", key="scan_anomaly_btn")
    if scan_btn and scan_nbhd:
        with st.spinner("Scanning neighborhood..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(agents["anomaly_agent"].scan_neighborhood(scan_nbhd, scan_district))
            loop.close()
        if result.get('error'):
            st.warning(result['error'])
        else:
            # Persist results in session state
            st.session_state['scan_results'] = result
            st.session_state['scan_nbhd_code'] = scan_nbhd
            st.session_state['scan_district_code'] = scan_district
            stats = result.get('stats', {})
            flagged = result.get('flagged', [])
            col1, col2, col3 = st.columns(3)
            col1.metric("Analyzed", stats.get('property_count', 0))
            col2.metric("Median $/ft²", f"${stats.get('median_pps', 0):,.0f}")
            col3.metric("🚨 Flagged", len(flagged))
            if flagged:
                st.success(f"Found {len(flagged)} over-assessed properties. See main area for details.")
    elif 'scan_results' in st.session_state:
        r = st.session_state['scan_results']
        stats = r.get('stats', {})
        flagged = r.get('flagged', [])
        st.info(f"Last scan: {st.session_state.get('scan_nbhd_code', '')} — {len(flagged)} flagged")

# ── Assessment Watch List ────────────────────────────────────────────
st.sidebar.divider()
with st.sidebar.expander("🔔 Assessment Monitor", expanded=False):
    st.caption("Track properties for annual assessment changes")

    # Initialize monitor
    from backend.services.assessment_monitor import AssessmentMonitor
    monitor = AssessmentMonitor()

    # Add property to watch
    watch_acct = st.text_input("Account to watch", placeholder="e.g. 0660460360030", key="watch_acct_input")
    watch_threshold = st.slider("Alert threshold (%)", 1, 25, 5, key="watch_threshold")
    if st.button("➕ Add to Watch List", key="add_watch_btn"):
        if watch_acct:
            with st.spinner("Adding..."):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(monitor.add_watch(watch_acct, district_code, watch_threshold))
                loop.close()
            if result.get('error'):
                st.warning(result['error'])
            else:
                change = result.get('change_pct', 0)
                st.success(f"Added! YoY change: {change:+.1f}%")

    # Show watch list
    loop2 = asyncio.new_event_loop()
    asyncio.set_event_loop(loop2)
    watches = loop2.run_until_complete(monitor.get_watch_list())
    loop2.close()

    if watches:
        st.markdown(f"**Watching {len(watches)} properties:**")
        alerts = [w for w in watches if w.get('alert_triggered')]
        if alerts:
            st.error(f"🚨 {len(alerts)} alert(s)!")

        for w in watches[:10]:
            acct = w.get('account_number', '')
            addr = (w.get('address', '') or '')[:25]
            change = w.get('change_pct')
            triggered = w.get('alert_triggered', False)

            if change is not None:
                color = "🔴" if change > 0 and triggered else ("🟢" if change <= 0 else "🟡")
                st.markdown(f"{color} **{acct}** {addr} → {change:+.1f}%")
            else:
                st.markdown(f"⚪ **{acct}** {addr}")

        if st.button("🔄 Refresh All", key="refresh_watches"):
            with st.spinner("Refreshing..."):
                loop3 = asyncio.new_event_loop()
                asyncio.set_event_loop(loop3)
                refresh_result = loop3.run_until_complete(monitor.refresh_all())
                loop3.close()
            st.success(f"Checked {refresh_result['checked']}, {refresh_result['alerts']} alerts")
            st.rerun()
    else:
        st.info("No properties being monitored yet.")

# ── Pitch Deck Generator ────────────────────────────────────────────
st.sidebar.divider()
with st.sidebar.expander("📑 Pitch Deck Generator", expanded=False):
    from backend.feature_registry import get_live_count
    feat_count = get_live_count()
    st.caption(f"Generate investor/customer PDF ({feat_count} features)")
    if st.button("📄 Generate Pitch Deck", key="gen_pitch_deck"):
        with st.spinner("Generating pitch deck..."):
            import subprocess, sys
            result = subprocess.run(
                [sys.executable, "-X", "utf8", "scripts/generate_pitch_deck.py"],
                capture_output=True, text=True, cwd="."
            )
        if result.returncode == 0:
            pdf_path = "outputs/Texas_Equity_AI_Pitch_Deck.pdf"
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    "⬇️ Download Pitch Deck",
                    data=pdf_bytes,
                    file_name="Texas_Equity_AI_Pitch_Deck.pdf",
                    mime="application/pdf",
                    key="download_pitch_deck"
                )
                st.success(f"Generated! {feat_count} features included.")
        else:
            st.error(f"Generation failed: {result.stderr[:200]}")

# Main Content
st.title("Property Tax Protest Dashboard")

# ── Neighborhood Scan Results Panel ──────────────────────────────────
if 'scan_results' in st.session_state:
    scan_r = st.session_state['scan_results']
    scan_stats = scan_r.get('stats', {})
    scan_flagged = scan_r.get('flagged', [])
    nbhd_code = st.session_state.get('scan_nbhd_code', '')
    scan_dist = st.session_state.get('scan_district_code', '')

    with st.expander(f"🔍 Scan Results: Neighborhood {nbhd_code} ({scan_dist}) — {len(scan_flagged)} flagged", expanded=True):
        st.markdown("""
        **How we detect anomalies:** 
        This engine compares every property in the neighborhood based on Assessed Price per Square Foot ($/ft²). 
        * **Z-Score:** Measures how many standard deviations a property's assessed value is above the neighborhood average. A Z-Score of +1.5 or higher strongly signals an unfair valuation.
        * **Percentile:** Shows where the property ranks in the neighborhood. E.g. the 95th percentile means the county valued this property higher than 95% of its neighbors per sqft.
        """)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Properties", scan_stats.get('property_count', 0))
        c2.metric("Median $/ft²", f"${scan_stats.get('median_pps', 0):,.0f}")
        c3.metric("Std Dev", f"${scan_stats.get('std_pps', 0):,.0f}")
        c4.metric("Flagged", len(scan_flagged), delta=f"{len(scan_flagged)} over-assessed", delta_color="inverse")

        if scan_flagged:
            df = pd.DataFrame(scan_flagged)

            # Define helper to get official district valuation URL for the account
            def get_district_url(dist, acct):
                dist = dist.upper() if dist else "HCAD"
                if dist == "TAD": return f"https://www.tad.org/property/{acct}"
                if dist == "CCAD": return f"https://www.collincad.org/propertysearch?prop={acct}"
                if dist == "DCAD": return f"https://www.dallascad.org/AcctDetailRes.aspx?ID={acct}"
                if dist == "TCAD": return f"https://travis.prodigycad.com/property-detail/{acct}"
                # HCAD's new Blazor portal blocks direct URL access to PropertyDetail with 403/404s, so link to the search page
                return "https://search.hcad.org/"

            df['Details'] = df['account_number'].apply(lambda x: get_district_url(scan_dist, x))

            display_cols = ['account_number', 'Details', 'address', 'pps', 'z_score', 'percentile', 'estimated_over_assessment']
            available_cols = [c for c in display_cols if c in df.columns]

            if available_cols:
                display_df = df[available_cols].copy()
                if 'pps' in display_df.columns:
                    display_df['pps'] = display_df['pps'].apply(lambda x: f"${x:,.0f}")
                if 'z_score' in display_df.columns:
                    display_df['z_score'] = display_df['z_score'].apply(lambda x: f"{x:.2f}")
                if 'percentile' in display_df.columns:
                    display_df['percentile'] = display_df['percentile'].apply(lambda x: f"{x:.0f}th")
                if 'estimated_over_assessment' in display_df.columns:
                    display_df['estimated_over_assessment'] = display_df['estimated_over_assessment'].apply(lambda x: f"${x:,.0f}")
                
                display_df.columns = [c.replace('_', ' ').title() for c in display_df.columns]
                
                st.dataframe(
                    display_df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Details": st.column_config.LinkColumn("Details", display_text="View Source")
                    }
                )

            st.caption("💡 Click 'Select' below to quickly start a protest for any flagged account.")
            
            # Use native Streamlit buttons to avoid full-page URL reloads
            cols = st.columns(3)
            for i, row in display_df.iterrows():
                acct = row['Account Number']
                with cols[i % 3]:
                    if st.button(f"Generate Packet for {acct} 🚀", key=f"gen_btn_{acct}"):
                        st.session_state['generate_account_prefill'] = acct
                        st.session_state['selected_suggestion'] = "" # Reset autocomplete

        st.divider()
        c_left, c_mid, c_right = st.columns([1,2,1])
        with c_mid:
            if st.button("⬅️ Back to Home (Clear Scan Results)", use_container_width=True, type="secondary"):
                del st.session_state['scan_results']
                st.rerun()

account_placeholder = "e.g. 0660460360030 (13 digits)"
if district_code == "TAD": account_placeholder = "e.g. 04657837 (8 digits)"
elif district_code == "CCAD": account_placeholder = "e.g. R-2815-00C-0100-1 or 2787425"
elif district_code == "TCAD": account_placeholder = "e.g. 123456 (select TCAD manually — not auto-detected)"
elif district_code == "DCAD": account_placeholder = "e.g. 00000776533000000 (17 digits)"

# ── Address Autocomplete / Input ──────────────────────────────────────────
account_number = None

try:
    from st_keyup import st_keyup
    st.write(f"**Enter {district_code} Account Number or Street Address**")
    
    # Store selected suggestion in session state to prevent loop reset
    if "selected_suggestion" not in st.session_state:
        st.session_state.selected_suggestion = ""
    if "last_search" not in st.session_state:
        st.session_state.last_search = ""
        
    # Pre-populate from session state if user clicked "Generate Packet" button from Anomaly Table
    prefill_val = st.session_state.get('generate_account_prefill', "")
        
    # The live input box (dynamic key forces component to remount when prefill changes)
    live_input = st_keyup(
        "", 
        value=prefill_val,
        placeholder=account_placeholder,
        key=f"account_input_live_{prefill_val}", 
        debounce=500
    )
    
    # Only fetch if there's sufficient text and it's mostly alphabetical (an address, not an account)
    if live_input and len(live_input) >= 5 and sum(c.isalpha() for c in live_input) > 2 and live_input != st.session_state.last_search:
        try:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": f"{live_input}, Texas", "format": "json", "addressdetails": 1, "limit": 5},
                headers={"User-Agent": "TexasEquityAI/1.0"},
                timeout=3
            )
            if resp.status_code == 200:
                results = resp.json()
                formatted_suggestions = []
                for res in results:
                    addr = res.get('address', {})
                    street_num = addr.get('house_number', '')
                    road = addr.get('road', '')
                    city = addr.get('city', addr.get('town', addr.get('village', '')))
                    zip_code = addr.get('postcode', '')
                    
                    # Construct clean '1200 Smith St, Houston, TX 77002'
                    street = f"{street_num} {road}".strip()
                    if street and city:
                        clean_addr = f"{street}, {city}, TX {zip_code}".strip(" ,")
                        if clean_addr not in formatted_suggestions:
                            formatted_suggestions.append(clean_addr)
                        
                st.session_state.suggestions = formatted_suggestions
        except Exception:
            pass # Silent fail to not disrupt UX
            
    if hasattr(st.session_state, 'suggestions') and st.session_state.suggestions and  live_input != st.session_state.selected_suggestion:
        selected = st.selectbox(
            "📍 Select Address Match", 
            [""] + st.session_state.suggestions,
            index=0,
            key="suggestion_dropdown"
        )
        if selected:
            st.session_state.selected_suggestion = selected
            st.session_state.last_search = live_input
            account_number = selected
            
    if not account_number:
        account_number = live_input
            
except ImportError:
    account_number = st.text_input(f"Enter {district_code} Account Number or Street Address", 
                                  placeholder=account_placeholder,
                                  key="account_input")

async def protest_generator_local(account_number, manual_address=None, manual_value=None, manual_area=None, district=None, force_fresh_comps=False):
    try:
        yield {"status": "🔍 Resolver Agent: Locating property and resolving address..."}
        current_account = account_number
        current_district = district
        rentcast_fallback_data = None

        is_address_input = any(c.isalpha() for c in account_number) and " " in account_number
        if is_address_input:
            # ── ID-First Resolution Chain ─────────────────────────────────────
            # Try to get an account ID from DB → RentCast → RealEstateAPI
            # before touching any scraper. Once we have an ID, scraping is
            # deterministic and immune to address abbreviation variations.
            resolved = await agents["bridge"].resolve_account_id(account_number, district)
            if resolved:
                current_account   = resolved["account_number"]
                current_district  = resolved.get("district") or current_district
                rentcast_fallback_data = resolved.get("rentcast_data")
                source = resolved.get("source", "?")
                conf   = resolved.get("confidence", 1.0)
                yield {"status": f"✅ Resolver [{source}]: Found account ID {current_account} (confidence {conf:.0%})"}
                logger.info(f"ID resolved via {source}: {account_number!r} → {current_account}")
            else:
                # All layers exhausted — fall through to scraper with a normalized address
                from backend.utils.address_utils import normalize_address_for_search
                normalized_input = normalize_address_for_search(account_number)
                if normalized_input and normalized_input != account_number:
                    current_account = normalized_input
                    logger.info(f"Resolver: no ID found, using normalized address for scraper: '{normalized_input}'")

        # Account-number format detection (always run to confirm district)
        detected_district = DistrictConnectorFactory.detect_district_from_account(current_account)
        if detected_district and detected_district != current_district:
            current_district = detected_district

        # DB district cross-check for already-known account numbers
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
        connector = DistrictConnectorFactory.get_connector(current_district, current_account)
        original_address = account_number if any(c.isalpha() for c in account_number) else None

        # Use cached data directly if it has REAL content — skip the scraper entirely
        # A valid cache record must have scraped key fields (year_built or neighborhood_code),
        # not just the old $450k placeholder defaults
        def is_valid_cache(rec):
            if not rec:
                return False
            has_real_value = rec.get('appraised_value') and rec.get('appraised_value') not in (450000, 0)
            has_real_area  = rec.get('building_area') and rec.get('building_area') != 2500
            has_year       = bool(rec.get('year_built'))
            has_nbhd       = bool(rec.get('neighborhood_code'))
            # Must have at least one rich field to be considered a real scrape
            return has_real_value or has_year or has_nbhd or has_real_area

        if (is_valid_cache(cached_property)
                and cached_property.get('address')
                and not manual_value and not manual_address):
            logger.info(f"Using Supabase cached record for {current_account} — skipping scraper.")
            property_details = cached_property
        else:
            if cached_property and not is_valid_cache(cached_property):
                logger.warning(f"Supabase cache for {current_account} looks like a ghost record (appraised={cached_property.get('appraised_value')}, year_built={cached_property.get('year_built')}, nbhd={cached_property.get('neighborhood_code')}) — forcing fresh scrape.")
            
            # ── Property Type Detection (multi-source chain) ────────────────
            from backend.agents.property_type_resolver import resolve_property_type
            is_likely_commercial = False
            ptype_source = "Unknown"
            ptype = "Unknown"

            # Fast path: if we already have RentCast cached data, check it first
            if rentcast_fallback_data:
                rc_ptype = (rentcast_fallback_data.get('rentcast_data') or {}).get('propertyType', '')
                if rc_ptype and rc_ptype not in ('Single Family', 'Condo', 'Townhouse', 'Manufactured', 'Multi-Family'):
                    is_likely_commercial = True
                    ptype_source = f"RentCast_Cached({rc_ptype})"
                elif rc_ptype:
                    ptype_source = f"RentCast_Cached({rc_ptype})"
                    # Confirmed residential — skip deeper checks

            # Full resolver chain if RentCast didn't give us a definitive answer
            if not rentcast_fallback_data or ptype_source == "Unknown":
                yield {"status": "🏢 Property Type Check: Resolving via multi-source chain..."}
                resolved_type, resolved_source = await resolve_property_type(
                    account_number=current_account,
                    address=current_account if any(c.isalpha() for c in current_account) else "",
                    district=prop_district if 'prop_district' in dir() else "HCAD",
                )
                ptype = resolved_type
                ptype_source = resolved_source
                is_likely_commercial = (resolved_type == "Commercial")
                logger.info(f"PropertyTypeResolver: {resolved_type} ({resolved_source}) for '{current_account}'")

            commercial_data = None
            if is_likely_commercial:
                from backend.agents.commercial_enrichment_agent import CommercialEnrichmentAgent
                yield {"status": f"🏢 Commercial Property Detected ({ptype_source}): Prioritizing commercial data sources..."}
                commercial_agent = CommercialEnrichmentAgent()
                commercial_data = await commercial_agent.enrich_property(current_account)
            
            if commercial_data and (commercial_data.get('appraised_value', 0) > 0 or commercial_data.get('building_area', 0) > 0):
                logger.info(f"Commercial Enrichment Successful — Skipping standard scraper. Value: ${commercial_data.get('appraised_value', 0)}")
                property_details = {
                    "account_number": commercial_data.get('account_number') or current_account,
                    "district": current_district or "HCAD",
                    "property_type": "commercial",
                    **commercial_data
                }
            else:
                # Standard Residential Flow (or fallback if commercial enrichment failed)
                if is_likely_commercial:
                     yield {"status": "⚠️ Commercial enrichment yielded limited data. Trying district portal..."}
                else:
                     yield {"status": f"⛏️ Residental Flow: Scraping {current_district or 'District'} records..."}
                
                property_details = await connector.get_property_details(current_account, address=original_address)
        
        if property_details and property_details.get('account_number'):
            current_account = property_details.get('account_number')
        
        if not property_details:
             # Final fallback: if standard scrape failed AND we have basic RentCast data
             if rentcast_fallback_data:
                property_details = rentcast_fallback_data
             else:
                yield {"error": f"Could not retrieve property data for '{current_account}'. Please try the Manual Override fields."}
                return

        # Inject resolved property type if it wasn't already set by a specific scraper
        ptype = locals().get('ptype', 'Unknown')
        ptype_source = locals().get('ptype_source', 'Unknown')
        if ptype != "Unknown" and 'property_type' not in property_details:
            property_details['property_type'] = ptype.lower()
        if ptype_source != "Unknown" and 'ptype_source' not in property_details:
            property_details['ptype_source'] = ptype_source

        raw_addr = property_details.get('address', '')
        district_context = property_details.get('district', 'HCAD')
        property_details['address'] = normalize_address(raw_addr, district_context)
        if manual_address: property_details['address'] = manual_address
        if manual_value: property_details['appraised_value'] = manual_value
        if manual_area: property_details['building_area'] = manual_area

        # ── Write to Supabase cache (so cloud runs can use locally-scraped data) ──
        if is_real_address(property_details.get('address', '')):
            try:
                clean_prop = {
                    "account_number": property_details.get("account_number"),
                    "address":        property_details.get("address"),
                    "appraised_value": property_details.get("appraised_value"),
                    "market_value":   property_details.get("market_value"),
                    "building_area":  property_details.get("building_area"),
                    "year_built":     property_details.get("year_built"),
                    "neighborhood_code": property_details.get("neighborhood_code"),
                    "district":       property_details.get("district"),
                }
                # Remove None values — Supabase rejects explicit nulls for some columns
                clean_prop = {k: v for k, v in clean_prop.items() if v is not None}
                await supabase_service.upsert_property(clean_prop)
                logger.info(f"Cached property {clean_prop.get('account_number')} to Supabase.")
            except Exception as e:
                logger.warning(f"Supabase cache write failed (non-fatal): {e}")


        # ── Market Value Resolution ────────────────────────────────────────
        # Priority: 1) DB market_value (HCAD authoritative), 2) Last sale price, 3) RentCast AVM
        # Known bad values: $999,999 is a RentCast API cap, not a real estimate
        SUSPICIOUS_VALUES = {999999, 9999999, 99999}  # API caps to reject

        db_market = float(property_details.get('market_value', 0) or 0)
        appraised_for_market = float(property_details.get('appraised_value', 0) or 0)

        if db_market > 0 and int(db_market) not in SUSPICIOUS_VALUES:
            # DB market value is authoritative (from HCAD bulk import)
            market_value = db_market
            logger.info(f"Using DB market value: ${market_value:,.0f}")
        else:
            # Fallback: try RentCast last sale or AVM
            market_value = appraised_for_market  # default to appraised
            prop_address = property_details.get('address', '')
            if is_real_address(prop_address):
                cached_market = await supabase_service.get_cached_market(current_account)
                if cached_market:
                    cached_val = cached_market.get('market_value', 0)
                    if cached_val and int(cached_val) not in SUSPICIOUS_VALUES:
                        market_value = cached_val
                        logger.info(f"Using cached market value: ${market_value:,.0f}")
                    else:
                        logger.warning(f"Rejected cached market value ${cached_val:,.0f} (suspicious API cap)")
                else:
                    try:
                        market_data = await agents["bridge"].get_last_sale_price(
                            prop_address, resolved_data=rentcast_fallback_data
                        )
                        if market_data and market_data.get('sale_price'):
                            sale_price = market_data['sale_price']
                            if int(sale_price) not in SUSPICIOUS_VALUES:
                                market_value = sale_price
                        if market_value == appraised_for_market:
                            avm_value = await agents["bridge"].get_estimated_market_value(
                                appraised_for_market, prop_address
                            )
                            if avm_value and int(avm_value) not in SUSPICIOUS_VALUES:
                                market_value = avm_value
                        # Save to cache
                        await supabase_service.save_cached_market(current_account, {'market_value': market_value})
                    except: pass

        prop_address = property_details.get('address', '')
        subject_permits = await agents["permit_agent"].get_property_permits(prop_address)
        permit_summary = agents["permit_agent"].analyze_permits(subject_permits)
        property_details['permit_summary'] = permit_summary
        yield {"status": "⚖️ Equity Specialist: Discovering comparable properties..."}
        try:
            if not is_real_address(prop_address):
                logger.warning(f"Address '{prop_address}' does not look like a real street address — skipping neighbor discovery. Portal scraping likely failed.")
                yield {"error": f"⚠️ Could not retrieve property details from the appraisal district portal. The address could not be resolved (got: '{prop_address}'). This may be due to Cloudflare blocking on the deployed server. Try running locally, or use the Manual Override fields to enter the address and value directly."}
                return

            real_neighborhood = []
            nbhd_code = property_details.get('neighborhood_code')
            bld_area  = int(property_details.get('building_area') or 0)
            prop_district = property_details.get('district', 'HCAD')

            def _detect_commercial(prop: dict) -> bool:
                """Detect commercial property from property_type string OR HCAD state class codes."""
                pt = str(prop.get('property_type', '') or '').lower().strip()

                # Literal type words (from most APIs / district portals)
                COMMERCIAL_KEYWORDS = {
                    'commercial', 'office', 'retail', 'industrial',
                    'mixed_use', 'mixed use', 'land', 'vacant',
                    'warehouse', 'restaurant', 'store', 'hotel', 'motel',
                    'bank', 'service', 'manufacturing', 'flex', 'apartment',
                }
                if any(kw in pt for kw in COMMERCIAL_KEYWORDS):
                    return True

                # HCAD state class codes → first letter signals property category
                # A=residential, B=mobile home, C=vacant, D=farm, E=exempt,
                # F=commercial, G=oil/gas, H=commercial, J=utilities, K=commercial
                COMMERCIAL_CODE_PREFIXES = ('F', 'G', 'H', 'J', 'K', 'L', 'X')
                import re as _re
                m = _re.match(r'^([A-Z])\d?$', pt.upper())
                if m and m.group(1) in COMMERCIAL_CODE_PREFIXES:
                    return True

                return False

            is_commercial_prop = _detect_commercial(property_details)

            # Ensure property_type is set so downstream agents (SalesAgent) classify correctly
            if is_commercial_prop and not property_details.get('property_type'):
                property_details['property_type'] = 'commercial'

            # ── Commercial properties: use API-based comp pool directly ───────
            if is_commercial_prop:
                try:
                    from backend.agents.commercial_enrichment_agent import CommercialEnrichmentAgent
                    commercial_agent = CommercialEnrichmentAgent()
                    yield {"status": "🏢 Commercial Equity: Building value pool from recent sales comparables..."}
                    comp_pool = commercial_agent.get_equity_comp_pool(
                        property_details.get('address', account_number), property_details
                    )
                    if comp_pool:
                        real_neighborhood = comp_pool
                        yield {"status": f"⚖️ Equity Specialist: Using {len(real_neighborhood)} commercial sales comps for analysis."}
                    else:
                        logger.warning("Commercial: Could not build sales comp pool from API.")
                except Exception as ce:
                    logger.error(f"Commercial comp pool error: {ce}")

            # ── Residential (or commercial fallback): DB-first then scrape ─────
            if not real_neighborhood:
                if is_commercial_prop:
                    yield {"status": "⚖️ Commercial fallback: Trying database comps..."}
                # Layer 0: DB-first lookup (fastest — no browser, works on cloud)
                if not force_fresh_comps and nbhd_code and bld_area > 0:
                    db_comps = await supabase_service.get_neighbors_from_db(
                        current_account, nbhd_code, bld_area, district=prop_district
                    )
                    if len(db_comps) >= 3:
                        real_neighborhood = db_comps
                        yield {"status": f"⚖️ Equity Specialist: Found {len(real_neighborhood)} comps from database instantly."}

                # Layer 1: Cached comps (previously scraped, TTL 30 days)
                if not real_neighborhood and not force_fresh_comps:
                    cached = await supabase_service.get_cached_comps(current_account)
                    if cached:
                        real_neighborhood = cached
                        yield {"status": f"⚖️ Equity Specialist: Using {len(real_neighborhood)} cached comps (< 30 days old)."}

            # ── Layers 2-3: Playwright scraping (residential only) ───────────────
            if not real_neighborhood and not is_commercial_prop:
                if force_fresh_comps:
                    yield {"status": "⚖️ Equity Specialist: Force-refreshing comps from live portal..."}
                else:
                    yield {"status": "⚖️ Equity Specialist: DB insufficient — scraping live neighbors..."}

                # Extract street name
                street_only = prop_address.split(",")[0].strip()
                addr_parts = street_only.split()
                if addr_parts and addr_parts[0][0].isdigit():
                    addr_parts = addr_parts[1:]
                KNOWN_CITIES = {
                    "HOUSTON", "DALLAS", "AUSTIN", "FORT", "WORTH", "PLANO",
                    "ARLINGTON", "IRVING", "GARLAND", "FRISCO", "MCKINNEY",
                    "SUGAR", "LAND", "KATY", "SPRING", "HUMBLE", "PEARLAND",
                    "PASADENA", "BAYTOWN", "LEAGUE", "CITY", "GALVESTON"
                }
                while addr_parts:
                    last = addr_parts[-1].upper().rstrip(".,")
                    if last.isdigit() and len(last) == 5:
                        addr_parts.pop()
                    elif last.isalpha() and len(last) == 2 and last.isupper():
                        addr_parts.pop()
                    elif last in KNOWN_CITIES:
                        addr_parts.pop()
                    else:
                        break
                street_name = " ".join(addr_parts)
                logger.info(f"Street discovery: extracted '{street_name}' from '{prop_address}'")

                async def scrape_pool(pool_list, limit=3):
                    sem = asyncio.Semaphore(limit)
                    async def safe_scrape(neighbor):
                        async with sem:
                            return await connector.get_property_details(neighbor['account_number'])
                    tasks = [safe_scrape(n) for n in pool_list[:10]]
                    deep_results = await asyncio.gather(*tasks)
                    return [res for res in deep_results if res and (res.get('building_area', 0) > 0 or res.get('appraised_value', 0) > 0)]

                # Street-level scrape
                discovered_neighbors = await connector.get_neighbors_by_street(street_name)
                if discovered_neighbors:
                    discovered_neighbors = [n for n in discovered_neighbors if n['account_number'] != property_details.get('account_number')]
                    real_neighborhood = await scrape_pool(discovered_neighbors)

                # Neighborhood code scrape fallback
                if not real_neighborhood:
                    is_nbhd_commercial = connector.is_commercial_neighborhood_code(nbhd_code) if nbhd_code else False
                    if is_nbhd_commercial:
                        logger.info(f"Neighborhood code '{nbhd_code}' is commercial — skipping neighborhood-wide search.")
                        yield {"error": f"⚠️ This appears to be a **commercial property** (Neighborhood Code: '{nbhd_code}'). Residential equity analysis requires comparable residential properties. Please verify the property type and try a manual address override if needed."}
                        return
                    elif nbhd_code and nbhd_code != "Unknown":
                        logger.info(f"Street search yielded 0 usable comps. Trying neighborhood code '{nbhd_code}'...")
                        nbhd_neighbors = await connector.get_neighbors(nbhd_code)
                        if nbhd_neighbors:
                            nbhd_neighbors = [n for n in nbhd_neighbors if n['account_number'] != property_details.get('account_number')]
                            real_neighborhood = await scrape_pool(nbhd_neighbors)

                # Save freshly scraped comps to cache
                if real_neighborhood:
                    try:
                        await supabase_service.save_cached_comps(current_account, real_neighborhood)
                    except Exception as e:
                        logger.warning(f"Failed to cache comps: {e}")

            # ── Final fallback: API-based sales comps (catches commercial misclassified as residential
            #    AND addresses like Hempstead Rd where street scraping returns nothing)
            if not real_neighborhood:
                try:
                    from backend.agents.commercial_enrichment_agent import CommercialEnrichmentAgent
                    commercial_agent_fb = CommercialEnrichmentAgent()
                    yield {"status": "🏢 Fallback Comps: Street scrape empty — querying API sales comps..."}
                    comp_pool_fb = commercial_agent_fb.get_equity_comp_pool(
                        property_details.get('address', account_number), property_details
                    )
                    if comp_pool_fb:
                        real_neighborhood = comp_pool_fb
                        yield {"status": f"⚖️ Equity Specialist: Recovered {len(real_neighborhood)} sales comps from API fallback."}
                except Exception as _fb_e:
                    logger.warning(f"Final comp fallback failed: {_fb_e}")

            if not real_neighborhood:
                yield {"error": "Could not find sufficient comparable properties for equity analysis. The property may be unique, commercial, or in a low-density area. Try using a manual address override."}
                return

            equity_results = agents["equity_engine"].find_equity_5(property_details, real_neighborhood)
            
            # Sales Comparison Analysis (independent data source)
            try:
                cached_sales = await supabase_service.get_cached_sales(current_account)
                if cached_sales:
                    yield {"status": "💰 Sales Specialist: Using cached sales comparables..."}
                    equity_results['sales_comps'] = cached_sales
                    equity_results['sales_count'] = len(cached_sales)
                    count = len(cached_sales)
                    yield {"status": f"💰 Sales Specialist: {count} cached comparable{'s' if count != 1 else ''}."}
                    logger.info(f"Sales Analysis: Using {count} cached comps.")
                else:
                    yield {"status": "💰 Sales Specialist: Searching for recent comparable sales..."}
                    sales_results = agents["equity_engine"].get_sales_analysis(property_details)
                    if sales_results:
                        equity_results['sales_comps'] = sales_results.get('sales_comps', [])
                        equity_results['sales_count'] = sales_results.get('sales_count', 0)
                        count = equity_results['sales_count']
                        yield {"status": f"💰 Sales Specialist: Found {count} comparable{'s' if count != 1 else ''}."}
                        logger.info(f"Sales Analysis: Found {count} comps.")
                        # Save to cache (serialize SalesComparable objects)
                        raw_sales = sales_results.get('sales_comps', [])
                        serializable = []
                        for sc in raw_sales:
                            if hasattr(sc, '__dict__'):
                                serializable.append({k: v for k, v in sc.__dict__.items() if not k.startswith('_')})
                            elif isinstance(sc, dict):
                                serializable.append(sc)
                        if serializable:
                            await supabase_service.save_cached_sales(current_account, serializable)
            except Exception as sales_err:
                logger.error(f"Sales Analysis Error: {sales_err}")
            
            property_details['comp_renovations'] = await agents["permit_agent"].summarize_comp_renovations(equity_results.get('equity_5', []))

            # ── Anomaly Detection: Score subject against neighborhood ────────
            try:
                nbhd_for_anomaly = property_details.get('neighborhood_code')
                dist_for_anomaly = property_details.get('district', 'HCAD')
                if nbhd_for_anomaly:
                    yield {"status": "📊 Anomaly Detector: Scoring property against neighborhood..."}
                    anomaly_score = await agents["anomaly_agent"].score_property(
                        current_account, nbhd_for_anomaly, dist_for_anomaly
                    )
                    if anomaly_score and not anomaly_score.get('error'):
                        equity_results['anomaly_score'] = anomaly_score
                        property_details['anomaly_score'] = anomaly_score
                        z = anomaly_score.get('z_score', 0)
                        pctile = anomaly_score.get('percentile', 0)
                        if z > 1.5:
                            yield {"status": f"🚨 Anomaly Detected: Property at {pctile:.0f}th percentile (Z={z:.1f})"}
                        elif z > 1.0:
                            yield {"status": f"📊 Elevated Assessment: Property at {pctile:.0f}th percentile (Z={z:.1f})"}
            except Exception as anomaly_err:
                logger.warning(f"Anomaly detection failed (non-fatal): {anomaly_err}")

            # ── Geo-Intelligence: Distance + External Obsolescence ────────
            try:
                from backend.services.geo_intelligence_service import (
                    enrich_comps_with_distance, check_external_obsolescence, geocode
                )
                prop_address_geo = property_details.get('address', '')
                equity_comps_geo = equity_results.get('equity_5', []) if isinstance(equity_results, dict) else []
                if equity_comps_geo and prop_address_geo:
                    yield {"status": "🌐 Geo-Intelligence: Computing distances..."}
                    subj_coords = geocode(prop_address_geo)
                    enrich_comps_with_distance(prop_address_geo, equity_comps_geo, subj_coords)
                    if subj_coords:
                        obs_result = check_external_obsolescence(subj_coords['lat'], subj_coords['lng'])
                        if obs_result.get('factors'):
                            equity_results['external_obsolescence'] = obs_result
                            property_details['external_obsolescence'] = obs_result
            except Exception as geo_err:
                logger.warning(f"Geo-intelligence failed (non-fatal): {geo_err}")

        except Exception as e:
            import traceback
            logger.error(f"Equity analysis failed: {e}\n{traceback.format_exc()}")
            equity_results = {"error": str(e)}

        yield {"status": "📸 Vision Agent: Analyzing property condition..."}
        search_address = property_details.get('address', '')
        flood_data = None
        coords = agents["vision_agent"]._geocode_address(search_address)
        if coords:
            # Cache-first: FEMA flood zone
            cached_flood = await supabase_service.get_cached_flood(current_account)
            if cached_flood:
                flood_data = cached_flood
                logger.info(f"Using cached flood zone: {flood_data.get('zone', 'N/A')}")
            else:
                flood_data = await agents["fema_agent"].get_flood_zone(coords['lat'], coords['lng'])
                if flood_data:
                    await supabase_service.save_cached_flood(current_account, flood_data)
            if flood_data: property_details['flood_zone'] = flood_data.get('zone', 'Zone X')

        # Cache-first: Vision analysis
        cached_vision = await supabase_service.get_cached_vision(current_account)
        if cached_vision and cached_vision.get('detections') is not None:
            logger.info(f"Using cached vision analysis for {current_account}")
            yield {"status": "📸 Vision Agent: Using cached property condition analysis..."}
            vision_detections = cached_vision.get('detections')
            image_paths = cached_vision.get('image_paths', [])
        else:
            image_paths = await agents["vision_agent"].get_street_view_images(search_address)
            vision_detections = await agents["vision_agent"].analyze_property_condition(image_paths, property_details)
            # Save to cache
            try:
                await supabase_service.save_cached_vision(current_account, {
                    'detections': vision_detections,
                    'image_paths': image_paths,
                })
            except Exception as vc_err:
                logger.warning(f"Vision cache save failed: {vc_err}")
        image_path = image_paths[0] if image_paths else "mock_street_view.jpg"
        # Annotate all images with bounding boxes
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

        # ── AI Comp Photo Comparison (Enhancement #1) ────────────────────────
        comp_images = None
        equity_comps = equity_results.get('equity_5', []) if isinstance(equity_results, dict) else []
        if equity_comps and image_paths:
            yield {"status": "🔍 AI Condition Analyst: Comparing property conditions across comps..."}
            try:
                comp_images = await agents["vision_agent"].fetch_comp_images(
                    subject_address=search_address,
                    subject_image_path=image_path,
                    comparables=equity_comps,
                    max_comps=5
                )
                n_fetched = len([k for k in (comp_images or {}) if not k.endswith('_condition') and k != 'subject'])
                logger.info(f"Comp photo comparison: {n_fetched} comp images fetched + analyzed")
            except Exception as e:
                logger.warning(f"Comp photo comparison failed (non-fatal): {e}")
                comp_images = None

        # ── Condition Delta Scoring ────────────────────────────────────────
        try:
            from backend.services.condition_delta_service import enrich_comps_with_condition
            equity_comps_cd = equity_results.get('equity_5', []) if isinstance(equity_results, dict) else []
            if equity_comps_cd and image_path and image_path != "mock_street_view.jpg":
                yield {"status": "📸 Condition Delta: Scoring subject vs comp conditions..."}
                property_details['vision_detections'] = vision_detections
                delta_result = await enrich_comps_with_condition(
                    property_details, equity_comps_cd,
                    agents["vision_agent"], subject_image_path=image_path
                )
                if delta_result:
                    equity_results['condition_delta'] = delta_result
                    delta_val = delta_result.get('condition_delta', 0)
                    if delta_val < -1:
                        yield {"status": f"📸 Condition Delta: Subject in worse condition (Δ={delta_val:.1f})"}
        except Exception as cd_err:
            logger.warning(f"Condition delta failed (non-fatal): {cd_err}")

        # ── Predictive Savings Estimation ─────────────────────────────────
        try:
            from backend.services.savings_estimator import SavingsEstimator
            estimator = SavingsEstimator(tax_rate=0.025)
            savings_prediction = estimator.estimate(property_details, equity_results)
            if isinstance(equity_results, dict):
                equity_results['savings_prediction'] = savings_prediction
            if savings_prediction.get('signal_count', 0) > 0:
                prob = savings_prediction.get('protest_success_probability', 0)
                exp_save = savings_prediction['estimated_savings']['expected']
                yield {"status": f"✨ Protest Strength: {savings_prediction['protest_strength']} ({prob:.0%}) — Expected savings: ${exp_save:,}/yr"}
        except Exception as se_err:
            logger.warning(f"Savings estimator failed (non-fatal): {se_err}")

        yield {"status": "✍️ Legal Narrator: Evaluating protest viability..."}

        # ── Protest Viability Gate ────────────────────────────────────────────
        # Only call the LLM if there is at least one valid protest argument.
        # This avoids wasting API credits and generating inaccurate narratives.
        appraised_val = property_details.get('appraised_value', 0) or 0
        justified_val = equity_results.get('justified_value_floor', 0) if isinstance(equity_results, dict) else 0
        justified_val = justified_val or 0

        has_equity_argument   = justified_val > 0 and appraised_val > justified_val
        has_market_argument   = market_value and market_value > 0 and appraised_val > market_value
        has_condition_issues  = bool(vision_detections and len(vision_detections) > 0)
        flood_zone            = property_details.get('flood_zone', 'Zone X')
        has_flood_risk        = flood_zone and 'Zone X' not in flood_zone
        
        # Sales comps viability check
        has_sales_argument = False
        sales_comps_for_viability = equity_results.get('sales_comps', []) if isinstance(equity_results, dict) else []
        if sales_comps_for_viability:
            try:
                sale_prices = [float(str(c.get('Sale Price','0')).replace('$','').replace(',','')) for c in sales_comps_for_viability]
                sale_prices = [p for p in sale_prices if p > 0]
                if sale_prices:
                    sale_prices.sort()
                    mid = len(sale_prices) // 2
                    median_sp = sale_prices[mid] if len(sale_prices) % 2 else (sale_prices[mid-1] + sale_prices[mid]) / 2
                    has_sales_argument = appraised_val > median_sp
            except: pass

        protest_viable = has_equity_argument or has_market_argument or has_condition_issues or has_flood_risk or has_sales_argument

        if protest_viable:
            reasons = []
            if has_equity_argument:   reasons.append(f"equity over-assessment (${appraised_val - justified_val:,.0f} gap)")
            if has_market_argument:   reasons.append(f"market value gap (${appraised_val - market_value:,.0f})")
            if has_sales_argument:    reasons.append(f"{len(sales_comps_for_viability)} sales comps support reduction")
            if has_condition_issues:  reasons.append(f"{len(vision_detections)} condition issue(s) detected")
            if has_flood_risk:        reasons.append(f"flood risk ({flood_zone})")
            logger.info(f"Protest viable — generating narrative. Reasons: {'; '.join(reasons)}")
            yield {"status": f"✍️ Legal Narrator: Generating protest narrative ({', '.join(reasons)})..."}
            narrative = agents["narrative_agent"].generate_protest_narrative(
                property_details, equity_results, vision_detections, market_value
            )
        else:
            logger.info("Protest not viable — skipping narrative agent (no over-assessment, no condition issues, no flood risk).")
            narrative = (
                "⚠️ No Protest Recommended Based on Current Data\n\n"
                "The analysis did not find grounds for a property tax protest at this time:\n\n"
                f"• Equity Analysis: The justified value of comparable properties "
                f"(${justified_val:,.0f}) is {'higher than' if justified_val > appraised_val else 'equal to'} "
                f"your appraised value (${appraised_val:,.0f}), indicating your property is not over-assessed "
                f"relative to its neighbors.\n"
                f"• Market Value: No significant gap detected between appraised and market values.\n"
                f"• Condition: No physical condition issues were identified from street-level imagery.\n"
                f"• Flood Risk: Property is in {flood_zone} (minimal risk).\n\n"
                "If you believe there are grounds for protest not captured here (e.g., interior condition, "
                "recent damage, or incorrect property data), use the Manual Override fields to provide "
                "corrected values and re-run the analysis."
            )

        # ── Unified Professional Protest Packet ───────────────────────────────────────────
        os.makedirs("outputs", exist_ok=True)
        combined_path = f"outputs/ProtestPacket_{current_account}.pdf"
        try:
            sales_comps_raw = equity_results.get('sales_comps', [])
            agents["pdf_service"].generate_evidence_packet(
                narrative, property_details, equity_results, vision_detections, combined_path,
                sales_data=sales_comps_raw, image_paths=annotated_paths,
                flood_data=flood_data,
                permit_data=property_details.get('permit_summary'),
                comp_renovations=property_details.get('comp_renovations', []),
                comp_images=comp_images  # AI Comp Photo Comparison data
            )
            logger.info(f"Professional Protest Packet generated: {combined_path}")
            pdf_error = None
        except Exception as e:
            logger.error(f"Unified PDF generation failed: {e}")
            combined_path = None
            pdf_error = str(e)
        
        # ── Data Persistence for QR Code (Enhancement #10) ────────────────────
        try:
            protest_record = {
                "account_number": current_account,
                "property_data": property_details,
                "equity_data": equity_results,
                "vision_data": vision_detections,
                "narrative": narrative,
                "market_value": market_value,
                "status": "complete"
            }
            saved = await supabase_service.save_protest(protest_record)
            if saved and equity_results.get('equity_5'):
                 await supabase_service.save_equity_comps(saved.get('id', current_account), equity_results.get('equity_5'))
            logger.info(f"Saved protest record for {current_account} to Supabase.")
        except Exception as db_err:
            logger.error(f"Failed to save protest record to DB: {db_err}")

        yield {"data": {
            "property": property_details, "market_value": market_value, "equity": equity_results,
            "vision": vision_detections, "narrative": narrative, "combined_pdf_path": combined_path,
            "pdf_error": pdf_error,
            "evidence_image_path": image_path,
            "all_image_paths": annotated_paths
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
                        manual_area=m_area if m_area > 0 else None, district=district_code,
                        force_fresh_comps=force_fresh_comps
                    ):
                        if "status" in chunk:
                            st.write(chunk["status"])
                        if "warning" in chunk: st.warning(chunk["warning"], icon="⚠️")
                        if "error" in chunk:
                            st.error(chunk["error"])
                            status.update(label="❌ Generation Failed", state="error", expanded=True)
                            return None
                        if "data" in chunk:
                            data = chunk["data"]
                    return data

                try:
                    final_data = loop.run_until_complete(main_loop())
                except Exception as e:
                    st.error(f"Generation Loop Failed: {e}")
                
                if final_data:
                    status.update(label="✅ Protest Packet Ready!", state="complete", expanded=False)

            # Check logic outside the status container (Dedent to 8 spaces)
            if final_data:
                data = final_data
                
                # Top-level button removed as per user request (moved back to Narrative tab)
                
                st.divider()
                
                tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🏠 Property", "⚖️ Equity", "💰 Sales Comps", "📸 Vision", "📄 Protest", "⚙️ Data"])
                with tab1:
                    col1, col2 = st.columns(2)
                    with col1: st.subheader("Details"); st.json(data['property'])
                    with col2:
                        st.subheader("Market Analysis")
                        appraised = data['property'].get('appraised_value', 0)
                        market = data['market_value']
                        st.metric("County Appraised Value", f"${appraised:,.0f}", help="The county's final appraised value after homestead caps or exemptions.")
                        st.metric("County Market Value", f"${market:,.0f}", delta=f"${market - appraised:,.0f} over cap", delta_color="inverse", help="The county's initial uncapped market assessment.")
                        
                        try:
                            # Safely attempt to parse out the AI opinion of value from the data payload
                            eq_floor = data.get('equity', {}).get('justified_value_floor', appraised) if isinstance(data.get('equity'), dict) else appraised
                            
                            ms = appraised
                            s_data = data.get('sales_comps', [])
                            if isinstance(s_data, list) and len(s_data) > 0:
                                prices = []
                                for sc in s_data:
                                    p = sc.get('sale_price', sc.get('Sale Price', 0)) if isinstance(sc, dict) else 0
                                    try: p = float(str(p).replace('$','').replace(',',''))
                                    except: p = 0
                                    if p > 0: prices.append(p)
                                if prices:
                                    prices.sort()
                                    ms = prices[len(prices)//2]
                            
                            opinion = min(appraised, eq_floor, ms) if ms > 0 else min(appraised, eq_floor)
                            
                            if opinion < appraised:
                                st.divider()
                                st.metric("AI Target Protest Value", f"${opinion:,.0f}", delta=f"-${appraised - opinion:,.0f} recommended reduction", delta_color="normal", help="The lowest defensible property value calculated by our AI based on equity and sales comparables.")
                        except Exception as e:
                            pass

                        val_hist = data['property'].get('valuation_history')
                        if val_hist:
                            if isinstance(val_hist, str):
                                import json
                                try:
                                    val_hist = json.loads(val_hist)
                                except:
                                    val_hist = None
                            
                            if val_hist and isinstance(val_hist, dict):
                                st.divider()
                                st.subheader("📈 Assessment History")
                                hist_rows = []
                                for year in sorted(val_hist.keys()):
                                    a_val = val_hist[year].get("appraised", 0)
                                    m_val = val_hist[year].get("market", 0)
                                    if a_val > 0 or m_val > 0:
                                        hist_rows.append({
                                            "Year": str(year),
                                            "Appraised": a_val,
                                            "Market": m_val
                                        })
                                
                                # Include current year's values 
                                current_yr = "2025"
                                if current_yr not in val_hist and appraised > 0:
                                    hist_rows.append({
                                        "Year": current_yr,
                                        "Appraised": appraised,
                                        "Market": market
                                    })
                                
                                if hist_rows:
                                    hist_df = pd.DataFrame(hist_rows)
                                    import plotly.express as px
                                    fig = px.bar(
                                        hist_df,
                                        x="Year",
                                        y=["Appraised", "Market"],
                                        barmode="stack",
                                        labels={"value": "Valuation", "variable": ""}
                                    )
                                    fig.update_layout(
                                        yaxis=dict(tickformat="$,.0f"),
                                        hovermode="x unified",
                                        xaxis_type='category'
                                    )
                                    fig.update_traces(hovertemplate="%{y:$,.0f}")
                                    st.plotly_chart(fig, use_container_width=True)
                with tab2:
                    st.subheader("Equity Analysis")
                    equity_has_data = data['equity'] and (
                        data['equity'].get('equity_5') or
                        data['equity'].get('justified_value_floor', 0) > 0
                    )
                    if not equity_has_data:
                        st.error("Equity analysis failed — no comparable properties could be found.")
                        if data['equity'] and data['equity'].get('error'):
                            st.caption(f"ℹ️ {data['equity']['error']}")
                    else:
                        justified_val = data['equity'].get('justified_value_floor', 0)
                        savings = max(0, appraised - justified_val)
                        c1, c2 = st.columns(2)
                        with c1: st.metric("Justified Value", f"${justified_val:,.0f}", delta=f"-${savings:,.0f}" if savings > 0 else None)
                        with c2: st.metric("💰 Est. Savings", f"${savings * (tax_rate/100):,.0f}")

                        if savings == 0 and justified_val > 0:
                            over_by = justified_val - appraised
                            st.info(
                                f"**No equity over-assessment found.** "
                                f"Your appraised value (\${appraised:,.0f}) is **\${over_by:,.0f} below** "
                                f"the median justified value of comparable properties (\${justified_val:,.0f}). "
                                f"This means your neighbors are assessed *higher* per square foot than you are — "
                                f"the equity argument does not support a reduction. "
                                f"Any protest would need to rely on market value, condition, or location factors instead.",
                                icon="ℹ️"
                            )
                        elif savings > 0:
                            st.success(
                                f"**Equity over-assessment detected!** "
                                f"Your appraised value (\${appraised:,.0f}) exceeds the justified value floor "
                                f"(\${justified_val:,.0f}) by **\${savings:,.0f}**. "
                                f"At a {tax_rate}% tax rate, this represents ~\${savings * (tax_rate/100):,.0f} in potential annual savings.",
                                icon="✅"
                            )

                        equity_df = pd.DataFrame(data['equity'].get('equity_5', []))
                        if not equity_df.empty:
                            # Ensure property_type column exists (Supabase omits null keys)
                            if 'property_type' not in equity_df.columns:
                                equity_df['property_type'] = 'Residential'
                            else:
                                equity_df['property_type'] = equity_df['property_type'].fillna('Residential')
                            # Select and rename display columns
                            display_cols = {
                                'address': 'Address',
                                'property_type': 'Type',
                                'appraised_value': 'Appraised Value',
                                'market_value': 'Market Value',
                                'building_area': 'Sq Ft',
                                'year_built': 'Year Built',
                                'value_per_sqft': '$/Sq Ft',
                                'similarity_score': 'Similarity',
                                'neighborhood_code': 'Nbhd Code',
                                'source': 'Source',
                            }
                            # Only keep columns that exist in the DataFrame
                            cols_to_show = {k: v for k, v in display_cols.items() if k in equity_df.columns}
                            equity_display = equity_df[list(cols_to_show.keys())].rename(columns=cols_to_show)

                            # Apply formatting
                            fmt = {}
                            if 'Appraised Value' in equity_display.columns:
                                fmt['Appraised Value'] = '${:,.0f}'
                            if 'Market Value' in equity_display.columns:
                                fmt['Market Value'] = '${:,.0f}'
                            if '$/Sq Ft' in equity_display.columns:
                                fmt['$/Sq Ft'] = '${:.2f}'
                            if 'Sq Ft' in equity_display.columns:
                                fmt['Sq Ft'] = '{:,.0f}'
                            if 'Similarity' in equity_display.columns:
                                fmt['Similarity'] = '{:.1f}%'

                            st.dataframe(
                                equity_display.style.format(fmt, na_rep='—'),
                                width='stretch',
                                hide_index=True
                            )
                        

                        # ── Map View ───────────────────────────────────────── (Moved map logic here if needed, or keep in Equity)

                        # ── Map View ─────────────────────────────────────────
                        st.subheader("📍 Comparable Properties Map")
                        import pydeck as pdk

                        # Geocode subject property
                        subject_addr = data['property'].get('address', '')
                        subject_coords = geocode_address(subject_addr)

                        # Geocode each comp
                        map_points = []
                        if subject_coords:
                            map_points.append({
                                "lat": subject_coords["lat"],
                                "lon": subject_coords["lon"],
                                "label": "Subject",
                                "address": subject_addr,
                                "appraised_value": f"${data['property'].get('appraised_value', 0):,.0f}",
                                "color": [220, 50, 50, 220],   # Red
                                "radius": 40,
                            })

                        for comp in data['equity'].get('equity_5', []):
                            comp_addr = comp.get('address', '')
                            if not comp_addr or comp_addr == 'Unknown':
                                continue
                            # Append district city for better geocoding accuracy
                            district_city_map = {
                                "HCAD": "Houston, TX", "TAD": "Fort Worth, TX",
                                "DCAD": "Dallas, TX", "TCAD": "Austin, TX", "CCAD": "Plano, TX"
                            }
                            district_key = data['property'].get('district', 'HCAD')
                            city_suffix = district_city_map.get(district_key, "Texas")
                            full_addr = comp_addr if any(c.isdigit() and len(comp_addr) > 10 for c in comp_addr) else f"{comp_addr}, {city_suffix}"
                            coords = geocode_address(full_addr)
                            if coords:
                                map_points.append({
                                    "lat": coords["lat"],
                                    "lon": coords["lon"],
                                    "label": "Comp",
                                    "address": comp_addr,
                                    "appraised_value": f"${comp.get('appraised_value', 0):,.0f}",
                                    "color": [30, 120, 220, 200],  # Blue
                                    "radius": 25,
                                })

                        if map_points:
                            map_df = pd.DataFrame(map_points)
                            center_lat = map_df["lat"].mean()
                            center_lon = map_df["lon"].mean()

                            layer = pdk.Layer(
                                "ScatterplotLayer",
                                data=map_df,
                                get_position=["lon", "lat"],
                                get_fill_color="color",
                                get_radius="radius",
                                radius_scale=6,
                                radius_min_pixels=8,
                                radius_max_pixels=30,
                                pickable=True,
                            )

                            view_state = pdk.ViewState(
                                latitude=center_lat,
                                longitude=center_lon,
                                zoom=calc_zoom_level(map_df),
                                pitch=0,
                            )

                            tooltip = {
                                "html": "<b>{label}</b><br/>{address}<br/>{appraised_value}",
                                "style": {"backgroundColor": "#1a1a2e", "color": "white", "fontSize": "13px", "padding": "8px"}
                            }

                            st.pydeck_chart(pdk.Deck(
                                layers=[layer],
                                initial_view_state=view_state,
                                tooltip=tooltip,
                                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                            ))


                            # Legend
                            st.caption("🔴 Subject Property &nbsp;&nbsp; 🔵 Comparable Properties")
                        else:
                            st.info("Map unavailable — could not geocode property addresses.")

                with tab3:
                    st.subheader("💰 Sales Comparable Analysis")
                    sales_comps = data['equity'].get('sales_comps', [])
                    if sales_comps:
                        # ── Parse key metrics ────────────────────────────────
                        sale_prices = []
                        sale_pps = []
                        for sc in sales_comps:
                            try:
                                p = float(str(sc.get('Sale Price', '0')).replace('$', '').replace(',', ''))
                                if p > 0: sale_prices.append(p)
                            except: pass
                            try:
                                pp = float(str(sc.get('Price/SqFt', '0')).replace('$', '').replace(',', ''))
                                if pp > 0: sale_pps.append(pp)
                            except: pass
                        
                        median_sale = 0
                        if sale_prices:
                            sale_prices.sort()
                            mid = len(sale_prices) // 2
                            median_sale = sale_prices[mid] if len(sale_prices) % 2 else (sale_prices[mid-1] + sale_prices[mid]) / 2
                        avg_pps = sum(sale_pps) / len(sale_pps) if sale_pps else 0
                        min_sale = min(sale_prices) if sale_prices else 0
                        max_sale = max(sale_prices) if sale_prices else 0
                        
                        # ── Key Metrics Row ──────────────────────────────────
                        c1, c2, c3, c4 = st.columns(4)
                        with c1:
                            sales_delta = median_sale - appraised if median_sale > 0 else None
                            st.metric("Median Sale Price", f"${median_sale:,.0f}", 
                                     delta=f"${sales_delta:,.0f}" if sales_delta else None,
                                     delta_color="inverse")
                        with c2:
                            st.metric("Avg $/SqFt", f"${avg_pps:.2f}")
                        with c3:
                            st.metric("Comps Found", f"{len(sales_comps)}")
                        with c4:
                            sales_savings = max(0, appraised - median_sale) if median_sale > 0 else 0
                            est_tax_savings = sales_savings * (tax_rate / 100)
                            st.metric("💰 Est. Tax Savings", f"${est_tax_savings:,.0f}")
                        
                        # ── Contextual Analysis ─────────────────────────────
                        if median_sale > 0 and appraised > median_sale:
                            gap = appraised - median_sale
                            st.success(
                                f"**Market over-appraisal detected!** "
                                f"Your appraised value (\${appraised:,.0f}) exceeds the median sale price "
                                f"of {len(sales_comps)} comparable sales (\${median_sale:,.0f}) by **\${gap:,.0f}**. "
                                f"Sales range: \${min_sale:,.0f} — \${max_sale:,.0f}. "
                                f"At a {tax_rate}% tax rate, this represents ~\${est_tax_savings:,.0f} in potential annual savings. "
                                f"This supports a protest under **Texas Tax Code §41.43(b)(3)** and **§23.01**.",
                                icon="✅"
                            )
                        elif median_sale > 0:
                            over_by = median_sale - appraised
                            st.info(
                                f"**No market over-appraisal found.** "
                                f"Your appraised value (\${appraised:,.0f}) is **\${over_by:,.0f} below** "
                                f"the median sale price of comparable properties (\${median_sale:,.0f}). "
                                f"Sales range: \${min_sale:,.0f} — \${max_sale:,.0f}. "
                                f"The sales comparison approach does not independently support a reduction, "
                                f"but this data can corroborate condition or equity-based arguments.",
                                icon="ℹ️"
                            )
                        
                        st.divider()
                        
                        # ── Data Table ────────────────────────────────────────
                        st.caption(f"**{len(sales_comps)} Most Recent Sales** — sorted by proximity")
                        sales_df = pd.DataFrame(sales_comps)
                        if not sales_df.empty:
                            # Format Sale Date column
                            if 'Sale Date' in sales_df.columns:
                                def format_sale_date(d):
                                    if not d or d == 'None' or str(d).strip() == '':
                                        return '—'
                                    try:
                                        from datetime import datetime as dt
                                        # Handle ISO format (2024-03-15T00:00:00) and plain dates
                                        date_str = str(d).split('T')[0]
                                        parsed = dt.strptime(date_str, '%Y-%m-%d')
                                        return parsed.strftime('%b %d, %Y')
                                    except:
                                        return str(d)
                                sales_df['Sale Date'] = sales_df['Sale Date'].apply(format_sale_date)
                            
                            sales_display_cols = {
                                'Address': 'Address',
                                'Type': 'Type',
                                'Sale Price': 'Sale Price',
                                'Sale Date': 'Sale Date',
                                'SqFt': 'Sq Ft',
                                'Price/SqFt': '$/Sq Ft',
                                'Year Built': 'Year Built',
                                'Distance': 'Distance',
                                'Source': 'Source'
                            }
                            s_cols_to_show = {k: v for k, v in sales_display_cols.items() if k in sales_df.columns}
                            sales_display = sales_df[list(s_cols_to_show.keys())].rename(columns=s_cols_to_show)
                            
                            st.dataframe(
                                sales_display,
                                width='stretch',
                                hide_index=True
                            )
                        
                        # ── Sales Comps Map ───────────────────────────────────
                        st.subheader("📍 Sales Comparable Map")
                        import pydeck as pdk

                        subject_addr = data['property'].get('address', '')
                        subject_coords = geocode_address(subject_addr)

                        sales_map_points = []
                        if subject_coords:
                            sales_map_points.append({
                                "lat": subject_coords["lat"],
                                "lon": subject_coords["lon"],
                                "label": "Subject",
                                "address": subject_addr,
                                "sale_price": f"Appraised: \${data['property'].get('appraised_value', 0):,.0f}",
                                "color": [220, 50, 50, 220],
                                "radius": 40,
                            })

                        for sc in sales_comps:
                            sc_addr = sc.get('Address', '')
                            if not sc_addr:
                                continue
                            sc_coords = geocode_address(sc_addr)
                            if sc_coords:
                                sales_map_points.append({
                                    "lat": sc_coords["lat"],
                                    "lon": sc_coords["lon"],
                                    "label": "Sale Comp",
                                    "address": sc_addr,
                                    "sale_price": sc.get('Sale Price', 'N/A'),
                                    "color": [50, 180, 80, 220],
                                    "radius": 25,
                                })

                        if sales_map_points:
                            sales_map_df = pd.DataFrame(sales_map_points)
                            center_lat = sales_map_df["lat"].mean()
                            center_lon = sales_map_df["lon"].mean()

                            layer = pdk.Layer(
                                "ScatterplotLayer",
                                data=sales_map_df,
                                get_position=["lon", "lat"],
                                get_fill_color="color",
                                get_radius="radius",
                                radius_scale=6,
                                radius_min_pixels=8,
                                radius_max_pixels=30,
                                pickable=True,
                            )

                            view_state = pdk.ViewState(
                                latitude=center_lat,
                                longitude=center_lon,
                                zoom=calc_zoom_level(sales_map_df),
                                pitch=0,
                            )

                            tooltip = {
                                "html": "<b>{label}</b><br/>{address}<br/>{sale_price}",
                                "style": {"backgroundColor": "#1a1a2e", "color": "white", "fontSize": "13px", "padding": "8px"}
                            }

                            st.pydeck_chart(pdk.Deck(
                                layers=[layer],
                                initial_view_state=view_state,
                                tooltip=tooltip,
                                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                            ))

                            st.caption("🔴 Subject Property &nbsp;&nbsp; 🟢 Sales Comparables")
                        else:
                            st.info("Map unavailable — could not geocode property addresses.")

                        # ── CSV Export ────────────────────────────────────────
                        csv_data = sales_df.to_csv(index=False)
                        st.download_button(
                            "⬇️ Export Sales Comps CSV",
                            csv_data,
                            file_name=f"salescomps_{data['property'].get('account_number', 'unknown')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning("No recent sales comparables found for this property.")

                with tab4:
                    st.subheader("📸 Condition Analysis")
                    vision_items = data.get('vision', [])
                    all_imgs = data.get('all_image_paths', [])
                    
                    # Separate summary object from issue detections
                    condition_summary = None
                    issues_only = []
                    if isinstance(vision_items, list):
                        for item in vision_items:
                            if isinstance(item, dict):
                                if item.get('issue') == 'CONDITION_SUMMARY':
                                    condition_summary = item
                                else:
                                    issues_only.append(item)
                    
                    # ── Condition Summary Metrics ───────────────────────────
                    if condition_summary:
                        c1, c2, c3, c4 = st.columns(4)
                        score = condition_summary.get('condition_score', 'N/A')
                        eff_age = condition_summary.get('effective_age', 'N/A')
                        with c1:
                            score_label = "🟢 Good" if isinstance(score, (int, float)) and score >= 7 else "🟡 Fair" if isinstance(score, (int, float)) and score >= 4 else "🔴 Poor"
                            st.metric("Condition Score", f"{score}/10 ({score_label})")
                        with c2:
                            st.metric("Effective Age", f"{eff_age} yrs")
                        with c3:
                            total_deductions = sum(i.get('deduction', 0) for i in issues_only)
                            st.metric("Total Deductions", f"${total_deductions:,.0f}")
                        with c4:
                            st.metric("Issues Found", f"{len(issues_only)}")
                    elif issues_only:
                        c1, c2 = st.columns(2)
                        total_deductions = sum(i.get('deduction', 0) for i in issues_only)
                        with c1: st.metric("Total Deductions", f"${total_deductions:,.0f}")
                        with c2: st.metric("Issues Found", f"{len(issues_only)}")
                    
                    # ── Depreciation Breakdown ─────────────────────────────
                    if issues_only:
                        physical = sum(i.get('deduction', 0) for i in issues_only if i.get('category', '').startswith('Physical'))
                        functional = sum(i.get('deduction', 0) for i in issues_only if i.get('category', '').startswith('Functional'))
                        external = sum(i.get('deduction', 0) for i in issues_only if i.get('category', '').startswith('External'))
                        
                        if any([physical, functional, external]):
                            st.divider()
                            st.caption("**Depreciation Breakdown (Texas Appraisal Categories)**")
                            dep_c1, dep_c2, dep_c3 = st.columns(3)
                            with dep_c1:
                                st.metric("Physical Deterioration", f"${physical:,.0f}")
                            with dep_c2:
                                st.metric("Functional Obsolescence", f"${functional:,.0f}")
                            with dep_c3:
                                st.metric("External Obsolescence", f"${external:,.0f}")
                        
                        st.divider()
                        
                        # ── Issue Cards ─────────────────────────────────────
                        st.caption(f"**{len(issues_only)} Condition Issues Identified**")
                        for issue in issues_only:
                            severity = issue.get('severity', 'Unknown')
                            sev_color = "🔴" if severity == "High" else "🟡" if severity == "Medium" else "🟢"
                            category = issue.get('category', 'Uncategorized')
                            confidence = issue.get('confidence', 0)
                            
                            with st.expander(f"{sev_color} **{issue.get('issue', 'Unknown')}** — {severity} | ${issue.get('deduction', 0):,.0f} | {category}", expanded=False):
                                st.write(issue.get('description', 'No description'))
                                conf_c1, conf_c2 = st.columns(2)
                                with conf_c1:
                                    st.progress(min(confidence, 1.0), text=f"Confidence: {confidence*100:.0f}%")
                                with conf_c2:
                                    st.caption(f"Category: {category}")
                    else:
                        st.info("No condition issues detected from Street View imagery. The property exterior appears to be in acceptable condition.", icon="ℹ️")
                    
                    # ── Multi-Image Gallery ─────────────────────────────────
                    st.divider()
                    st.caption("**Street View Images** — Front, Left 45°, Right 45°")
                    valid_imgs = [p for p in all_imgs if p and os.path.exists(p)]
                    if valid_imgs:
                        img_cols = st.columns(len(valid_imgs))
                        labels = ["Front", "Left 45°", "Right 45°"]
                        for idx, img_path in enumerate(valid_imgs):
                            with img_cols[idx]:
                                label = labels[idx] if idx < len(labels) else f"Angle {idx+1}"
                                st.image(img_path, caption=label, width='stretch')
                    elif os.path.exists(data.get('evidence_image_path', '')):
                        st.image(data['evidence_image_path'], caption="Front View", width=600)
                    else:
                        st.warning("No Street View images available for this property.")

                with tab5:
                    st.subheader("📄 Protest Summary")
                    
                    # ── Condition-Adjusted Recommended Value ──────────────
                    appraised = data['property'].get('appraised_value', 0) or 0
                    justified = data['equity'].get('justified_value_floor', 0) if isinstance(data.get('equity'), dict) else 0
                    justified = justified or 0
                    mkt = data.get('market_value', 0) or 0
                    
                    # Calculate vision deductions
                    vision_items = data.get('vision', [])
                    total_vision_deduction = 0
                    if isinstance(vision_items, list):
                        for vi in vision_items:
                            if isinstance(vi, dict) and vi.get('issue') != 'CONDITION_SUMMARY':
                                total_vision_deduction += vi.get('deduction', 0)
                    
                    # Base value = lowest of appraised, justified (if valid), market (if valid)
                    candidates = [appraised]
                    if justified > 0: candidates.append(justified)
                    if mkt > 0: candidates.append(mkt)
                    base_value = min(candidates)
                    recommended_value = max(0, base_value - total_vision_deduction)
                    total_savings = max(0, appraised - recommended_value)
                    
                    rc1, rc2, rc3 = st.columns(3)
                    with rc1:
                        st.metric("🏠 Current Appraised", f"${appraised:,.0f}")
                    with rc2:
                        st.metric(
                            "🎯 Recommended Protest Value", 
                            f"${recommended_value:,.0f}",
                            delta=f"-${total_savings:,.0f}" if total_savings > 0 else None,
                            delta_color="inverse"
                        )
                    with rc3:
                        if total_vision_deduction > 0:
                            st.metric("🔧 Condition Deduction", f"-${total_vision_deduction:,.0f}")
                        else:
                            st.metric("🔧 Condition Deduction", "$0")
                    
                    if total_savings > 0:
                        st.success(f"**Potential tax savings: ${total_savings * (tax_rate/100):,.0f}/year** based on a recommended protest value of ${recommended_value:,.0f} (base: ${base_value:,.0f} minus ${total_vision_deduction:,.0f} condition deduction).")
                    
                    st.divider()
                    st.subheader("Narrative")
                    st.info(data['narrative'])
                    pdf_path = data.get('combined_pdf_path', '')
                    pdf_error = data.get('pdf_error')
                    if pdf_path and os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                "📥 Download Complete Protest Packet",
                                f.read(),
                                file_name=f"ProtestPacket_{data['property'].get('account_number', 'unknown')}.pdf",
                                mime="application/pdf",
                                type="primary"
                            )
                    elif pdf_error:
                        st.error(f"❌ PDF Generation Failed: {pdf_error}")
                    else:
                        st.warning(f"⚠️ Protest PDF not found. (Path: {pdf_path or 'None'})")
                        st.caption("Please check the logs or try regenerating the packet.")
                with tab6: st.json(data)
