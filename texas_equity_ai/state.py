"""
Central application state — replaces all st.session_state usage.
Every attribute here is reactive: when changed, the UI auto-updates.
"""
import reflex as rx
import os
import sys
import json
import asyncio
import logging
import re

# Configure logging so backend agent logs show in the reflex run console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Ensure project root is on path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load env vars (API keys etc.)
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"), override=False)

logger = logging.getLogger(__name__)

# ── District detection helper (ported from app.py lines 530-576) ────
DISTRICT_OPTIONS = ["HCAD", "TAD", "CCAD", "DCAD", "TCAD"]

ACCOUNT_PLACEHOLDERS = {
    "HCAD": "e.g. 0660460360030 (13 digits)",
    "TAD": "e.g. 04657837 (8 digits)",
    "CCAD": "e.g. R-2815-00C-0100-1 or 2787425",
    "TCAD": "e.g. 123456 (select TCAD manually)",
    "DCAD": "e.g. 00000776533000000 (17 digits)",
}


def detect_district(raw_acc: str) -> str | None:
    """Auto-detect appraisal district from account number format."""
    if not raw_acc:
        return None
    clean = raw_acc.replace("-", "").replace(" ", "").strip()
    target = None

    # 1. Account number format
    if len(clean) == 17:
        target = "DCAD"
    elif len(clean) == 13 and clean.isdigit():
        target = "HCAD"
    elif raw_acc.upper().strip().startswith("R") and len(clean) <= 10:
        target = "CCAD"
    elif len(clean) == 8 and clean.isdigit():
        target = "TAD"

    # 2. City name fallback
    if not target and any(c.isalpha() for c in raw_acc):
        lower = raw_acc.lower()
        city_map = {
            "dallas": "DCAD", "austin": "TCAD", "fort worth": "TAD",
            "plano": "CCAD", "houston": "HCAD", "travis": "TCAD",
            "tarrant": "TAD", "harris": "HCAD",
        }
        for city, dist in city_map.items():
            if city in lower:
                target = dist
                break

    # 3. ZIP code fallback
    if not target:
        zip_map = {"750": "CCAD", "77": "HCAD", "75": "DCAD", "76": "TAD", "787": "TCAD", "786": "TCAD"}
        zip_match = re.search(r'\b(7\d{4})\b', raw_acc)
        if zip_match:
            z = zip_match.group(1)
            for prefix, dist in zip_map.items():
                if z.startswith(prefix):
                    target = dist
                    break
    return target


class AppState(rx.State):
    """Global application state."""

    # ── Input state ─────────────────────────────────────────────────
    account_number: str = ""
    district_code: str = "HCAD"
    manual_address: str = ""
    manual_value: float = 0.0
    manual_area: float = 0.0
    tax_rate: float = 2.5
    sidebar_collapsed: bool = False
    force_fresh: bool = False

    # ── Generation state ────────────────────────────────────────────
    is_generating: bool = False
    generation_complete: bool = False
    agent_logs: list[str] = []
    error_message: str = ""

    # ── Result data ─────────────────────────────────────────────────
    # pdf_path, evidence_image_path, all_image_paths, pitch_deck_path
    # store BASENAMES only (plain strings). Computed vars below resolve
    # them to /_upload/<basename> URLs for the frontend.
    property_data: dict = {}
    equity_data: dict = {}
    vision_data: list[dict] = []
    narrative: str = ""
    market_value: float = 0.0
    pdf_path: str = ""
    pdf_error: str = ""

    @rx.var
    def debug_property_json(self) -> str:
        try:
            return json.dumps(self.property_data, indent=2, default=str)
        except Exception:
            return str(self.property_data)

    @rx.var
    def debug_equity_json(self) -> str:
        try:
            return json.dumps(self.equity_data, indent=2, default=str)
        except Exception:
            return str(self.equity_data)

    @rx.var
    def debug_vision_json(self) -> str:
        if not self.vision_data:
            return "No vision detections available. This may mean:\n• No street view images were found for this property\n• The AI condition analysis did not detect any issues\n• The condition analysis step was skipped or timed out"
        try:
            return json.dumps(self.vision_data, indent=2, default=str)
        except Exception:
            return str(self.vision_data)
    evidence_image_path: str = ""
    all_image_paths: list[str] = []


    # ── Scan / monitor state ────────────────────────────────────────
    scan_results: dict = {}
    scan_nbhd_code: str = ""
    scan_district: str = "HCAD"
    watch_list: list[dict] = []
    watch_account: str = ""

    @rx.var
    def scan_flagged(self) -> list[dict]:
        return self.scan_results.get("flagged", []) if isinstance(self.scan_results, dict) else []

    @rx.var
    def scan_stats(self) -> dict:
        return self.scan_results.get("stats", {}) if isinstance(self.scan_results, dict) else {}
    pitch_deck_path: str = ""

    # ── Report viewer state (for /report/[account]) ─────────────────
    report_account: str = ""
    report_property: dict = {}
    report_protest: dict = {}
    report_anomaly: dict = {}

    # ── Computed properties ─────────────────────────────────────────
    @rx.var
    def account_placeholder(self) -> str:
        return ACCOUNT_PLACEHOLDERS.get(self.district_code, "Enter account number")

    @rx.var
    def has_results(self) -> bool:
        return bool(self.property_data)

    @rx.var
    def appraised_value(self) -> float:
        v = self.property_data.get("appraised_value", 0)
        try:
            return float(str(v).replace("$", "").replace(",", "").strip())
        except Exception:
            return 0.0

    @rx.var
    def justified_value(self) -> float:
        v = self.equity_data.get("justified_value_floor", 0)
        try:
            return float(v) if v else 0.0
        except Exception:
            return 0.0

    @rx.var
    def equity_savings(self) -> float:
        return max(0, self.appraised_value - self.justified_value)

    @rx.var
    def tax_savings(self) -> float:
        return self.equity_savings * (self.tax_rate / 100)

    @rx.var
    def sales_median_price(self) -> float:
        """Median sale price from sales comps."""
        raw = self.equity_data.get("sales_comps", []) if isinstance(self.equity_data, dict) else []
        prices = []
        for sc in raw:
            try:
                p = float(str(sc.get("Sale Price", "0")).replace("$", "").replace(",", ""))
                if p > 0:
                    prices.append(p)
            except (ValueError, TypeError):
                continue
        if not prices:
            return 0.0
        prices.sort()
        mid = len(prices) // 2
        return prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) / 2

    @rx.var
    def sales_savings(self) -> float:
        return max(0, self.appraised_value - self.sales_median_price) if self.sales_median_price > 0 else 0.0

    @rx.var
    def equity_comps(self) -> list[dict]:
        raw = self.equity_data.get("equity_5", []) if isinstance(self.equity_data, dict) else []
        formatted = []
        for c in raw:
            comp = dict(c)
            # Round $/sqft to 2 decimals
            try:
                comp["value_per_sqft"] = f"{float(comp.get('value_per_sqft', 0)):,.2f}"
            except (ValueError, TypeError):
                comp["value_per_sqft"] = "0.00"
            # Convert similarity (L2 distance → percentage: lower distance = higher similarity)
            try:
                raw_sim = float(comp.get("similarity") or comp.get("similarity_score") or 0)
                if raw_sim > 0:
                    # L2 distance: 0 = identical, ~2 = very different
                    pct = max(0, (1 - raw_sim) * 100)
                    comp["similarity_score"] = f"{pct:.0f}%"
                else:
                    comp["similarity_score"] = "—"
            except (ValueError, TypeError):
                comp["similarity_score"] = "—"
            # Format currency values
            try:
                comp["appraised_value"] = f"{float(comp.get('appraised_value', 0)):,.0f}"
            except (ValueError, TypeError):
                comp["appraised_value"] = "0"
            try:
                mv = float(comp.get("market_value") or comp.get("appraised_value", "0").replace(",", ""))
                comp["market_value"] = f"{mv:,.0f}"
            except (ValueError, TypeError):
                comp["market_value"] = comp.get("appraised_value", "0")
            # Format building area
            try:
                comp["building_area"] = f"{int(float(comp.get('building_area', 0))):,}"
            except (ValueError, TypeError):
                comp["building_area"] = "0"
            # Safe defaults
            comp.setdefault("comp_source", "local")
            comp.setdefault("neighborhood_code", "—")
            comp.setdefault("address", "Unknown")
            comp.setdefault("year_built", "—")
            comp.setdefault("property_type", "Residential")
            formatted.append(comp)
        return formatted

    @rx.var
    def sales_comps(self) -> list[dict]:
        raw = self.equity_data.get("sales_comps", []) if isinstance(self.equity_data, dict) else []
        formatted = []
        for c in raw:
            comp = dict(c)
            # Format sale date to readable format
            raw_date = str(comp.get("Sale Date", "") or "")
            if raw_date and raw_date != "None":
                try:
                    from datetime import datetime as dt
                    date_str = raw_date.split("T")[0]
                    parsed = dt.strptime(date_str, "%Y-%m-%d")
                    comp["Sale Date"] = parsed.strftime("%b %d, %Y")
                except Exception:
                    comp["Sale Date"] = raw_date
            else:
                comp["Sale Date"] = "—"
            # Format Sale Price as currency
            raw_price = str(comp.get("Sale Price", "") or "")
            if raw_price and raw_price != "—":
                try:
                    num = float(raw_price.replace("$", "").replace(",", ""))
                    comp["Sale Price"] = f"${num:,.0f}"
                except (ValueError, TypeError):
                    pass
            # Format Price/SqFt
            raw_pps = str(comp.get("Price/SqFt", "") or "")
            if raw_pps and raw_pps != "—":
                try:
                    num = float(raw_pps.replace("$", "").replace(",", ""))
                    comp["Price/SqFt"] = f"${num:,.2f}"
                except (ValueError, TypeError):
                    pass
            # Format SqFt
            raw_sqft = comp.get("SqFt", "")
            if raw_sqft and raw_sqft != "—":
                try:
                    comp["SqFt"] = f"{int(float(str(raw_sqft).replace(',', ''))):,}"
                except (ValueError, TypeError):
                    pass
            # Safe defaults
            comp.setdefault("Address", "Unknown")
            comp.setdefault("Sale Price", "—")
            comp.setdefault("SqFt", "—")
            comp.setdefault("Price/SqFt", "—")
            comp.setdefault("Year Built", "—")
            comp.setdefault("Distance", "—")
            formatted.append(comp)
        return formatted

    @rx.var
    def fmt_win_probability(self) -> str:
        """AI Win Predictor percentage from ML prediction."""
        ml = self.equity_data.get("ml_prediction", {}) if isinstance(self.equity_data, dict) else {}
        if not ml:
            return "—"
        return str(ml.get("win_probability_pct", "—"))

    @rx.var
    def condition_issues(self) -> list[dict]:
        """Vision items excluding the CONDITION_SUMMARY meta-entry."""
        if not isinstance(self.vision_data, list):
            return []
        return [v for v in self.vision_data if isinstance(v, dict) and v.get("issue") != "CONDITION_SUMMARY"]

    @rx.var
    def condition_summary_item(self) -> dict:
        if not isinstance(self.vision_data, list):
            return {}
        for v in self.vision_data:
            if isinstance(v, dict) and v.get("issue") == "CONDITION_SUMMARY":
                return v
        return {}

    @rx.var
    def total_vision_deduction(self) -> float:
        return sum(i.get("deduction", 0) for i in self.condition_issues)

    @rx.var
    def target_protest_value(self) -> float:
        candidates = [self.appraised_value]
        if self.justified_value > 0:
            candidates.append(self.justified_value)
        if self.market_value > 0:
            candidates.append(self.market_value)
        base = min(candidates)
        return max(0, base - self.total_vision_deduction)

    @rx.var
    def total_savings(self) -> float:
        return max(0, self.appraised_value - self.target_protest_value)

    @rx.var
    def fmt_appraised(self) -> str:
        return f"${self.appraised_value:,.0f}"

    @rx.var
    def fmt_target_protest(self) -> str:
        return f"${self.target_protest_value:,.0f}"

    @rx.var
    def fmt_justified(self) -> str:
        return f"${self.justified_value:,.0f}" if self.justified_value > 0 else "N/A"

    @rx.var
    def fmt_market(self) -> str:
        return f"${self.market_value:,.0f}" if self.market_value > 0 else "N/A"

    @rx.var
    def fmt_savings(self) -> str:
        return f"-${self.total_savings:,.0f}" if self.total_savings > 0 else ""

    @rx.var
    def fmt_equity_savings(self) -> str:
        return f"${self.equity_savings:,.0f}" if self.equity_savings > 0 else "$0"

    @rx.var
    def fmt_sales_median_price(self) -> str:
        return f"${self.sales_median_price:,.0f}" if self.sales_median_price > 0 else "$0"

    @rx.var
    def fmt_tax_savings(self) -> str:
        s = self.total_savings * (self.tax_rate / 100)
        return f"${s:,.0f}" if s > 0 else "$0"

    @rx.var
    def external_obsolescence_factors(self) -> list[dict]:
        obs = self.property_data.get("external_obsolescence", {})
        if not isinstance(obs, dict):
            obs = self.equity_data.get("external_obsolescence", {})
        return obs.get("factors", []) if isinstance(obs, dict) else []

    @rx.var
    def map_url(self) -> str:
        """Build a Google Static Maps URL using addresses (no lat/lon needed)."""
        api_key = os.getenv("GOOGLE_STREET_VIEW_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        if not api_key:
            return ""

        from urllib.parse import quote

        markers = []
        # Subject property — red marker
        subject_addr = self.property_data.get("address", "")
        if subject_addr and subject_addr != "Unknown":
            markers.append(f"markers=color:red%7Clabel:S%7C{quote(subject_addr)}")

        # Equity comps — blue markers
        for comp in self.equity_comps:
            addr = comp.get("address", "")
            if addr and addr != "Unknown" and addr != subject_addr:
                markers.append(f"markers=color:blue%7Clabel:C%7C{quote(addr)}")

        if not markers:
            return ""

        marker_str = "&".join(markers)
        return f"https://maps.googleapis.com/maps/api/staticmap?size=640x400&maptype=roadmap&{marker_str}&key={api_key}"

    # ── Event handlers ──────────────────────────────────────────────

    def set_account_number(self, value: str):
        self.account_number = value
        detected = detect_district(value)
        if detected and detected != self.district_code:
            self.district_code = detected

    def set_district(self, value: str):
        self.district_code = value

    def toggle_sidebar(self):
        self.sidebar_collapsed = not self.sidebar_collapsed

    def set_manual_address(self, value: str):
        self.manual_address = value

    def set_manual_value(self, value: str):
        try:
            self.manual_value = float(value) if value else 0.0
        except ValueError:
            self.manual_value = 0.0

    def set_manual_area(self, value: str):
        try:
            self.manual_area = float(value) if value else 0.0
        except ValueError:
            self.manual_area = 0.0

    def set_tax_rate(self, value: list):
        self.tax_rate = float(value[0]) if isinstance(value, list) else float(value)

    def toggle_force_fresh(self, value: bool):
        self.force_fresh = value

    def clear_results(self):
        """Reset all result state for a new generation."""
        self.property_data = {}
        self.equity_data = {}
        self.vision_data = []
        self.narrative = ""
        self.market_value = 0.0
        self.pdf_path = ""
        self.pdf_error = ""
        self.evidence_image_path = ""
        self.all_image_paths = []
        self.error_message = ""
        self.agent_logs = []
        self.generation_complete = False

    def start_generate(self):
        """Instantly set loading state, then kick off background task."""
        if self.is_generating:
            return
        if not self.account_number:
            self.error_message = "Please enter an account number or address."
            return
        self.clear_results()
        self.is_generating = True
        return AppState.generate_protest

    @rx.event(background=True)
    async def generate_protest(self):
        """Main protest generation — runs as background task."""

        # Capture state before background work
        async with self:
            acct = self.account_number
            dist = self.district_code
            m_addr = self.manual_address or None
            m_val = self.manual_value if self.manual_value > 0 else None
            m_area = self.manual_area if self.manual_area > 0 else None
            fresh = self.force_fresh
            rate = self.tax_rate

        try:
            from texas_equity_ai.services.protest_service import run_protest_pipeline

            async for update in run_protest_pipeline(
                account_number=acct,
                district=dist,
                manual_address=m_addr,
                manual_value=m_val,
                manual_area=m_area,
                force_fresh_comps=fresh,
                tax_rate=rate,
            ):
                if "status" in update:
                    async with self:
                        self.agent_logs = self.agent_logs + [update["status"]]
                if "warning" in update:
                    async with self:
                        self.agent_logs = self.agent_logs + [f"⚠️ {update['warning']}"]
                if "error" in update:
                    async with self:
                        self.error_message = update["error"]
                        self.is_generating = False
                    return
                if "data" in update:
                    data = update["data"]
                    async with self:
                        self.property_data = data.get("property", {})
                        self.equity_data = data.get("equity", {})
                        self.vision_data = data.get("vision", [])
                        self.narrative = data.get("narrative", "")
                        self.market_value = float(data.get("market_value", 0) or 0)
                        # Store basenames only — resolve to URLs at render time
                        self.pdf_path = data.get("combined_pdf_path", "") or ""
                        self.pdf_error = data.get("pdf_error", "") or ""
                        self.evidence_image_path = data.get("evidence_image_path", "") or ""
                        self.all_image_paths = data.get("all_image_paths", [])
                        self.generation_complete = True
                        self.is_generating = False

        except Exception as e:
            import traceback
            logger.error(f"Generation error: {traceback.format_exc()}")
            async with self:
                self.error_message = f"Generation failed: {str(e)}"
                self.is_generating = False

    @rx.event(background=True)
    async def run_anomaly_scan(self):
        """Run neighborhood anomaly scan as background task."""
        async with self:
            if not self.scan_nbhd_code:
                return
            nbhd = self.scan_nbhd_code
            dist = self.scan_district
            self.agent_logs = self.agent_logs + [f"🔍 Scanning neighborhood {nbhd}..."]

        try:
            from backend.agents.anomaly_detector import AnomalyDetectorAgent
            agent = AnomalyDetectorAgent()
            result = await agent.scan_neighborhood(nbhd, dist)
            async with self:
                if result.get("error"):
                    self.error_message = result["error"]
                else:
                    self.scan_results = result
        except Exception as e:
            async with self:
                self.error_message = f"Scan failed: {e}"

    async def load_report(self):
        """Load report data for the /report/[account] page."""
        if not self.report_account:
            return
        try:
            from backend.db.supabase_client import supabase_service
            prop = await supabase_service.get_property_by_account(self.report_account)
            protest = await supabase_service.get_latest_protest(self.report_account)
            self.report_property = prop or {}
            self.report_protest = protest or {}
        except Exception as e:
            logger.error(f"Report load error: {e}")
        yield

    # ── Sidebar tool handlers ───────────────────────────────────────

    def set_scan_nbhd_code(self, value: str):
        self.scan_nbhd_code = value

    def set_scan_district(self, value: str):
        self.scan_district = value

    def set_watch_account(self, value: str):
        self.watch_account = value

    @rx.event(background=True)
    async def add_to_watch_list(self):
        """Add a property to the assessment watch list."""
        async with self:
            if not self.watch_account:
                return
            acct = self.watch_account
            dist = self.district_code

        try:
            from backend.services.assessment_monitor import AssessmentMonitor
            monitor = AssessmentMonitor()
            result = await monitor.add_watch(acct, dist, 5)
            async with self:
                if result.get("error"):
                    self.error_message = result["error"]
                else:
                    self.watch_list = await monitor.get_watch_list()
                    self.watch_account = ""
        except Exception as e:
            async with self:
                self.error_message = f"Watch add failed: {e}"

    @rx.event(background=True)
    async def refresh_watch_list(self):
        """Refresh all watched properties."""
        try:
            from backend.services.assessment_monitor import AssessmentMonitor
            monitor = AssessmentMonitor()
            await monitor.refresh_all()
            watches = await monitor.get_watch_list()
            async with self:
                self.watch_list = watches
        except Exception as e:
            async with self:
                self.error_message = f"Refresh failed: {e}"

    @rx.event(background=True)
    async def generate_pitch_deck(self):
        """Generate the investor pitch deck PDF."""
        try:
            import subprocess
            upload_dir = str(rx.get_upload_dir())
            os.makedirs(upload_dir, exist_ok=True)
            pdf_path = os.path.join(upload_dir, "Texas_Equity_AI_Pitch_Deck.pdf")
            
            # Pass custom output path to script via env var
            env = os.environ.copy()
            env["PITCH_DECK_OUTPUT_PATH"] = pdf_path
            
            result = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-X", "utf8", "scripts/generate_pitch_deck.py"],
                capture_output=True, text=True,
                cwd=project_root, env=env
            )
            async with self:
                if result.returncode == 0 and os.path.exists(pdf_path):
                    self.pitch_deck_path = "Texas_Equity_AI_Pitch_Deck.pdf"
                else:
                    self.error_message = f"Pitch deck failed: {result.stderr[:200]}"
        except Exception as e:
            async with self:
                self.error_message = f"Pitch deck error: {e}"

