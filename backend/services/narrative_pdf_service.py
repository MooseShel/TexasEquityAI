import os
import datetime
import io
from google import genai
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from fpdf import FPDF
import logging
import re

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

def clean_text(text: str) -> str:
    """Replace non-latin-1 characters with ASCII equivalents, preserving spaces."""
    if not text:
        return ""
    replacements = {
        # Smart quotes
        "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
        "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
        # Dashes
        "\u2013": "-", "\u2014": "-", "\u2015": "-",
        # Other punctuation
        "\u2026": "...", "\u2022": "*", "\u00b7": "*",
        "\u00a7": "Sect.", "\u00a9": "(C)", "\u00ae": "(R)", "\u2122": "(TM)",
        # Unicode spaces
        "\u00a0": " ", "\u2009": " ", "\u200a": " ", "\u2002": " ",
        "\u2003": " ", "\u202f": " ", "\u205f": " ", "\u3000": " ",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text.encode('latin-1', 'replace').decode('latin-1')

logger = logging.getLogger(__name__)

class NarrativeAgent:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.xai_key = os.getenv("XAI_API_KEY")
        self.gemini_client = None
        self.openai_llm = None
        self.xai_llm = None

        if self.gemini_key:
            try:
                self.gemini_client = genai.Client(api_key=self.gemini_key)
                logger.info("Gemini Client initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")

        if self.openai_key:
            try:
                self.openai_llm = ChatOpenAI(model="gpt-4o-mini", api_key=self.openai_key, temperature=0.7)
            except: pass

        if self.xai_key:
            try:
                self.xai_llm = ChatOpenAI(model="grok-2-latest", api_key=self.xai_key, base_url="https://api.x.ai/v1", temperature=0.7)
            except: pass

    def generate_protest_narrative(self, property_data: dict, equity_data: dict, vision_data: list, market_value: float = None) -> str:
        if not self.gemini_client and not self.openai_llm and not self.xai_llm:
            return "Narrative Generation Unavailable: No LLM keys found."

        appraised_val = property_data.get('appraised_value', 0) or 0
        justified_val = equity_data.get('justified_value_floor', 0) if isinstance(equity_data, dict) else 0
        market_val = market_value or appraised_val

        equity_situation = f"Appraised: ${appraised_val:,.0f} | Justified: ${justified_val:,.0f}"

        inputs = {
            "address": property_data.get('address', 'N/A'),
            "account_number": property_data.get('account_number', 'N/A'),
            "appraised_value": f"{appraised_val:,.0f}",
            "building_area": property_data.get('building_area', 0),
            "market_value": f"{market_val:,.0f}",
            "justified_value": f"{justified_val:,.0f}",
            "comparables": ", ".join([c.get('address', 'N/A') for c in equity_data.get('equity_5', [])]) if isinstance(equity_data, dict) else "None",
            "sales_comp_count": 0, "median_sale_price": "N/A", "avg_sale_pps": "N/A", "sales_comps_detail": "N/A",
            "condition_score": "N/A", "effective_age": "N/A", "issues_detail": "None identified",
            "total_physical": "0", "total_functional": "0", "total_external": "0", "total_deduction": "0",
            "subject_permits": "N/A", "comp_renovations": "N/A", "flood_zone": "N/A",
            "equity_situation": equity_situation, "equity_argument": "", "sales_situation": "", "sales_argument": ""
        }

        if self.openai_llm:
            try:
                prompt = PromptTemplate.from_template("Write a professional protest for {address} justifying reduction to ${justified_value}. Cite Texas Tax Code §41.43(b)(1). \n\nData Summary: {equity_situation}")
                chain = prompt | self.openai_llm | StrOutputParser()
                return clean_text(chain.invoke(inputs))
            except: pass

        return "Protest Narrative: Subject property is over-assessed relative to neighbors."


class PDFService:
    """
    Generates a professional property tax evidence packet matching the format
    used by professional protest firms at Harris County ARB hearings.
    """

    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_STREET_VIEW_API_KEY")

    def _fmt(self, val) -> str:
        """Format a numeric value as currency."""
        if val is None or val == 0: return "$0"
        try: return f"${float(val):,.0f}"
        except: return str(val)

    def _parse_val(self, val):
        if not val: return 0
        if isinstance(val, (int, float)): return val
        return float(str(val).replace('$', '').replace(',', ''))

    def _pps(self, value, area):
        """Price per sqft."""
        v = self._parse_val(value)
        a = self._parse_val(area)
        if a > 0: return f"${v/a:,.2f}"
        return "N/A"

    # ── Header / Footer ──────────────────────────────────────────────────────
    def _draw_header(self, pdf, property_data, title):
        pdf.set_fill_color(30, 41, 59)
        pdf.rect(0, 0, 210, 25, 'F')
        pdf.set_xy(10, 5)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, clean_text(title), ln=True)
        pdf.set_font("Arial", '', 9)
        pdf.cell(0, 5, clean_text(f"Property: {property_data.get('address')}  |  Account: {property_data.get('account_number')}"), ln=True)
        pdf.set_text_color(0, 0, 0)
        # Reset fill color so the dark header doesn't bleed into subsequent cells
        pdf.set_fill_color(255, 255, 255)
        pdf.set_y(30)


    # ── Map Generation ────────────────────────────────────────────────────────
    def _generate_static_map(self, subject_addr: str, comp_addresses: list, label_color: str = "blue") -> str:
        if not self.google_api_key: return None
        try:
            import requests as req
            import tempfile
            markers = [f"color:red|label:S|{subject_addr}"]
            for i, addr in enumerate(comp_addresses[:7]):
                markers.append(f"color:{label_color}|label:{chr(65+i)}|{addr}")
            url = f"https://maps.googleapis.com/maps/api/staticmap?size=640x400&maptype=roadmap&key={self.google_api_key}&" + "&".join([f"markers={m}" for m in markers])
            resp = req.get(url, timeout=10)
            if resp.status_code == 200:
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False); tmp.write(resp.content); tmp.close()
                return tmp.name
        except: pass
        return None

    # ── Table Helpers ─────────────────────────────────────────────────────────
    def _generate_methodology_page(self, pdf, property_data):
        """Generates the 'Our Unique AI Approach' methodology page."""
        pdf.add_page()
        self._draw_header(pdf, property_data, "OUR AI-POWERED METHODOLOGY")
        
        # Title
        pdf.set_font("Arial", 'B', 14)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 10, "How We Build Your Protest Evidence", ln=True)
        pdf.ln(2)
        
        # Intro Text
        pdf.set_font("Arial", '', 10)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 5, clean_text(
            "Unlike traditional generic protests, your report was generated by a squad of specialized "
            "Artificial Intelligence agents working together to analyze your property from every angle. "
            "We combine government data, market sales, and computer vision to build the strongest possible argument."
        ))
        pdf.ln(8)

        # Section 1: The AI Squad
        pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 12)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 8, "1. The AI Squad: Multi-Agent Intelligence", ln=True)
        
        pdf.set_font("Arial", '', 9)
        pdf.set_text_color(0, 0, 0)
        
        # Bullet 1: Equity Agent
        pdf.set_x(15)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(35, 6, "Equity Agent:", 0, 0)
        pdf.set_font("Arial", '', 9)
        pdf.multi_cell(0, 6, clean_text(
            "Scans thousands of neighborhood properties to identify the fairest equity comparables. "
            "We mathematically prove if you are being taxed unequally compared to neighbors."
        ))
        
        # Bullet 2: Vision Agent (Machine Vision)
        pdf.set_x(15)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(35, 6, "Vision Agent:", 0, 0)
        pdf.set_font("Arial", '', 9)
        pdf.multi_cell(0, 6, clean_text(
            "Uses advanced Computer Vision & Machine Learning to analyze street-view imagery of your property. "
            "It detects condition issues (roof wear, peeling paint, cracks) that can justify a lower value."
        ))
        
        # Bullet 3: Sales Agent
        pdf.set_x(15)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(35, 6, "Sales Agent:", 0, 0)
        pdf.set_font("Arial", '', 9)
        pdf.multi_cell(0, 6, clean_text(
            "Retrieves recent market sales data to ensure your appraised value aligns with true market reality."
        ))
        pdf.ln(5)

        # Section 2: Legal Strategy
        pdf.set_font("Arial", 'B', 12)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 8, "2. Legal Strategy & Uniformity", ln=True)
        pdf.set_font("Arial", '', 10)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 5, clean_text(
            "Our primary argument leverages Texas Tax Code Section 41.43(b)(1), the 'Equity Uniformity' statute. "
            "The law mandates that you cannot be taxed at a higher level than comparable properties in your neighborhood. "
            "Even if your market value is accurate, if your neighbors are valued lower, you deserve a reduction."
        ))
        pdf.ln(6)

        # Section 3: Benefit Calculation
        pdf.set_font("Arial", 'B', 12)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 8, "3. True Tax Savings Calculation", ln=True)
        pdf.set_font("Arial", '', 10)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 5, clean_text(
            "A lower value doesn't always mean lower taxes if you have exemptions (like Homestead). "
            "Our system calculates your potential 'Actual Tax Savings' by factoring in your specific exemptions "
            "and local tax rates. We focus on putting real money back in your pocket, not just changing a number."
        ))
        pdf.ln(8)
        
        # Footer / Tagline
        pdf.set_draw_color(59, 130, 246)
        pdf.set_font("Arial", 'I', 9)
        pdf.cell(0, 5, clean_text("Powered by Texas Equity AI - Fair Taxation through Technology"), align='C')

    def _table_header(self, pdf, widths, headers, fill_color=(220, 225, 235)):
        pdf.set_fill_color(*fill_color)
        pdf.set_font("Arial", 'B', 7)
        for i, h in enumerate(headers):
            pdf.cell(widths[i], 7, clean_text(h), 1, 0, 'C', True)
        pdf.ln()

    def _table_row(self, pdf, widths, values, bold_first=True, fill_first=True, align='C'):
        pdf.set_font("Arial", size=7)
        for i, v in enumerate(values):
            is_first = (i == 0)
            if is_first and bold_first:
                pdf.set_font("Arial", 'B', 7)
            else:
                pdf.set_font("Arial", '', 7)
            fill = fill_first and is_first
            if fill:
                pdf.set_fill_color(245, 245, 250)
            cell_align = 'L' if is_first else align
            
            # Less aggressive truncation
            raw_text = clean_text(str(v))
            if len(raw_text) > 45:
                text_val = raw_text[:42] + "..."
            else:
                text_val = raw_text
                
            pdf.cell(widths[i], 7, text_val, 1, 0, cell_align, fill)
        pdf.ln()

    # ══════════════════════════════════════════════════════════════════════════
    # ██  MAIN PDF GENERATOR
    # ══════════════════════════════════════════════════════════════════════════
    def generate_evidence_packet(self, narrative: str, property_data: dict, equity_data: dict,
                                  vision_data: list, output_path: str, sales_data: list = None,
                                  image_paths: list = None, flood_data: dict = None,
                                  permit_data: dict = None, comp_renovations: list = None,
                                  comp_images: dict = None):
        pdf = FPDF()
        today = datetime.datetime.now().strftime("%m/%d/%Y")
        comps = equity_data.get('equity_5', [])
        appraised = self._parse_val(property_data.get('appraised_value', 0))
        market_val = self._parse_val(property_data.get('market_value', 0)) or appraised
        subj_area = self._parse_val(property_data.get('building_area', 0)) or 1
        subj_land = self._parse_val(property_data.get('land_value', 0))
        # Estimate land value from valuation history if not direct
        if not subj_land:
            hist = property_data.get('valuation_history', {})
            if hist:
                latest = sorted(hist.keys(), reverse=True)[0]
                subj_land = self._parse_val(hist[latest].get('land_appraised', 0))

        # ── PAGE 1: COVER PAGE ────────────────────────────────────────────────
        pdf.add_page()
        pdf.set_fill_color(30, 41, 59)
        pdf.rect(0, 0, 210, 297, 'F')
        pdf.set_text_color(255, 255, 255)

        pdf.set_font("Arial", 'B', 32)
        pdf.ln(60)
        pdf.cell(0, 20, "PROPERTY TAX", ln=True, align='C')
        pdf.set_font("Arial", 'B', 36)
        pdf.cell(0, 20, "EVIDENCE PACKET", ln=True, align='C')

        pdf.ln(15)
        pdf.set_font("Arial", '', 16)
        pdf.cell(0, 10, clean_text(f"Tax Year {property_data.get('tax_year', '2025')} Protest Submission"), ln=True, align='C')

        pdf.set_draw_color(59, 130, 246)
        pdf.set_line_width(1.5)
        pdf.line(40, 130, 170, 130)

        pdf.ln(40)
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, clean_text(f"SUBJECT: {property_data.get('address', 'Unknown')}"), ln=True, align='C')
        pdf.set_font("Arial", '', 14)
        pdf.cell(0, 10, f"Account Number: {property_data.get('account_number', 'N/A')}", ln=True, align='C')

        # ── QR Code (Enhancement #10) ────────────────────────────────────────
        if HAS_QRCODE:
            try:
                acct = property_data.get('account_number', '').replace('-', '')
                # Use query param for Streamlit routing
                qr_url = f"https://texasequityai.streamlit.app/?account={acct}"
                qr = qrcode.QRCode(version=1, box_size=6, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
                qr.add_data(qr_url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="white", back_color=(30, 41, 59))
                qr_path = f"data/qr_{acct}.png"
                os.makedirs("data", exist_ok=True)
                qr_img.save(qr_path)
                pdf.image(qr_path, x=82, y=195, w=45)
                pdf.set_y(243)
                pdf.set_font("Arial", '', 8)
                pdf.cell(0, 5, "Scan for interactive digital evidence", ln=True, align='C')
            except Exception as qr_err:
                logger.warning(f"QR code generation failed: {qr_err}")

        pdf.set_y(255)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 6, "CONFIDENTIAL EVIDENCE SUMMARY", ln=True, align='C')
        pdf.cell(0, 6, "Prepared for Appraisal Review Board", ln=True, align='C')
        pdf.set_text_color(0, 0, 0)

        # ── PAGE 1B: OUR UNIQUE AI APPROACH (METHODOLOGY) ────────────────────
        self._generate_methodology_page(pdf, property_data)

        # ── PAGE 2: ACCOUNT HISTORY ──────────────────────────────────────────
        pdf.add_page()
        self._draw_header(pdf, property_data, "ACCOUNT HISTORY")

        # Date of Report
        pdf.set_font("Arial", '', 8)
        pdf.set_xy(150, 30)
        pdf.cell(50, 5, f"Date of Report: {today}", align='R')
        pdf.set_y(36)

        # ── Owner & Subject Property Information ──
        pdf.set_fill_color(220, 225, 235)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(0, 7, "  Owner and Subject Property Information", ln=True, fill=True)
        pdf.set_font("Arial", '', 8)

        owner_name = property_data.get('owner_name', '')
        # HCAD hides owner names on portal — show account-based fallback if not available
        if not owner_name or owner_name.strip().lower() in ('on file', ''):
            owner_name = f"Account: {property_data.get('account_number', 'See Records')}"
        mailing_addr = property_data.get('mailing_address', '')
        if not mailing_addr or mailing_addr.strip().lower() in ('on file', ''):
            mailing_addr = "See HCAD Records"
        legal_desc = property_data.get('legal_description', '')
        land_use_code = property_data.get('land_use_code', '1001')
        land_use_desc = property_data.get('land_use_desc', 'Residential Single Family')
        cad_name = property_data.get('district', 'Harris')

        info_w = [38, 57, 38, 57]
        rows = [
            ("Account Number:", property_data.get('account_number', 'N/A'), "CAD:", cad_name),
            ("Owner Name:", clean_text(owner_name)[:30], "Site Address:", clean_text(property_data.get('address', 'N/A'))[:30]),
            ("Mailing Address:", clean_text(mailing_addr)[:30] if mailing_addr else "On File", "Legal Desc:", clean_text(legal_desc)[:30] if legal_desc else "N/A"),
            ("Land Use Code:", str(land_use_code), "Land Use Desc:", clean_text(land_use_desc)[:30]),
        ]
        for r in rows:
            pdf.set_font("Arial", 'B', 7)
            pdf.cell(info_w[0], 6, r[0], 0)
            pdf.set_font("Arial", '', 7)
            pdf.cell(info_w[1], 6, r[1], 0)
            pdf.set_font("Arial", 'B', 7)
            pdf.cell(info_w[2], 6, r[2], 0)
            pdf.set_font("Arial", '', 7)
            pdf.cell(info_w[3], 6, r[3], 0)
            pdf.ln()

        pdf.ln(3)

        # ── Current Value Breakdown ──
        subj_impr_front = max(0, appraised - subj_land)
        pdf.set_fill_color(220, 225, 235)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(0, 7, "  Current Value Breakdown", ln=True, fill=True)
        vb_w = [63, 64, 63]
        vb_heads = ["Land Value", "Improvement Value", "Total Appraised Value"]
        pdf.set_font("Arial", 'B', 7)
        for i, h in enumerate(vb_heads):
            pdf.cell(vb_w[i], 7, h, 1, 0, 'C', True)
        pdf.ln()
        pdf.set_font("Arial", '', 8)
        pdf.cell(vb_w[0], 7, self._fmt(subj_land) if subj_land else "See History", 1, 0, 'C')
        pdf.cell(vb_w[1], 7, self._fmt(subj_impr_front) if subj_impr_front else "See History", 1, 0, 'C')
        pdf.cell(vb_w[2], 7, self._fmt(appraised), 1, 0, 'C')
        pdf.ln()

        pdf.ln(3)

        # ── Physical Attributes Table ──
        pdf.set_fill_color(220, 225, 235)
        pdf.set_font("Arial", 'B', 8)
        pa_w = [24, 24, 24, 24, 24, 24, 24, 24]
        pa_heads = ["Land Area", "Total Bldg", "NRA", "Bldg Class", "Grade", "NBHD/Econ", "Key Map", "Year Built"]
        for i, h in enumerate(pa_heads):
            pdf.cell(pa_w[i], 7, h, 1, 0, 'C', True)
        pdf.ln()
        pdf.set_font("Arial", '', 7)
        land_area_val = property_data.get('land_area', 0)
        nbhd = property_data.get('neighborhood_code', 'N/A')
        grade = property_data.get('building_grade', 'N/A')
        key_map = property_data.get('key_map', '')
        pa_vals = [
            f"{land_area_val:,.0f} SF" if land_area_val else "N/A",
            f"{subj_area:,.0f} SF",
            "-",
            property_data.get('building_class', 'Excellent') if grade and grade.startswith('A') else property_data.get('building_class', 'Good'),
            str(grade),
            str(nbhd),
            str(key_map) if key_map else "-",
            str(property_data.get('year_built', 'N/A'))
        ]
        for i, v in enumerate(pa_vals):
            pdf.cell(pa_w[i], 7, clean_text(str(v))[:14], 1, 0, 'C')
        pdf.ln()

        pdf.ln(4)

        # ── Valuation History Table ──
        history = property_data.get('valuation_history', {})
        if history:
            pdf.set_fill_color(220, 225, 235)
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(0, 7, "  Valuation History", ln=True, fill=True)
            hist_w = [20, 25, 25, 25, 25, 25, 25, 21]
            hist_heads = ["Year", "Land Val", "Impr. Val", "Market", "PSF", "Appraised", "Change %", "Cap %"]
            pdf.set_font("Arial", 'B', 7)
            for i, h in enumerate(hist_heads):
                pdf.cell(hist_w[i], 7, h, 1, 0, 'C', True)
            pdf.ln()

            sorted_years = sorted(history.keys(), reverse=True)[:5]
            prev_mkt = None
            pdf.set_font("Arial", '', 7)
            for yr in reversed(sorted_years):
                v = history[yr]
                mkt = self._parse_val(v.get('market', 0))
                appr = self._parse_val(v.get('appraised', 0))
                l_val = self._parse_val(v.get('land_appraised', 0))
                i_val = self._parse_val(v.get('improvement_appraised', 0))

                change_pct = "---"
                if prev_mkt and prev_mkt > 0:
                    pct = ((mkt - prev_mkt) / prev_mkt) * 100
                    change_pct = f"{pct:+.1f}%"
                prev_mkt = mkt

                imp_area = subj_area if subj_area > 1 else 1
                psf = f"${mkt / imp_area:,.2f}" if mkt > 0 else "---"

                # Homestead cap: 10% max increase
                cap_pct = "---"
                if appr > 0 and mkt > 0 and appr != mkt:
                    cap_pct = f"{((appr/mkt)*100):.0f}%"

                vals = [yr, self._fmt(l_val) if l_val else "Pending", self._fmt(i_val) if i_val else "Pending",
                        self._fmt(mkt), psf, self._fmt(appr), change_pct, cap_pct]
                for i_idx, val in enumerate(vals):
                    pdf.cell(hist_w[i_idx], 7, str(val), 1, 0, 'C')
                pdf.ln()

        # ── Land Breakdown ──
        if property_data.get('land_breakdown'):
            pdf.ln(3)
            pdf.set_fill_color(220, 225, 235)
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(0, 7, "  Detailed Land Records", ln=True, fill=True)
            lw = [70, 40, 40, 40]
            l_heads = ["Use Code / Description", "Land Area", "Appraised Value", "Market Value"]
            pdf.set_font("Arial", 'B', 7)
            for i, h in enumerate(l_heads): pdf.cell(lw[i], 7, h, 1, 0, 'C', True)
            pdf.ln()
            pdf.set_font("Arial", '', 7)
            for entry in property_data['land_breakdown']:
                pdf.cell(lw[0], 7, clean_text(entry.get('use', 'Res')), 1)
                pdf.cell(lw[1], 7, f"{entry.get('units', 0):,} SF", 1, 0, 'C')
                pdf.cell(lw[2], 7, self._fmt(subj_land) if subj_land else "N/A", 1, 0, 'C')
                pdf.cell(lw[3], 7, self._fmt(subj_land) if subj_land else "N/A", 1, 0, 'C')
            pdf.ln()



        # ── PAGE 3: OPINION OF VALUE ─────────────────────────────────────────
        pdf.add_page()
        self._draw_header(pdf, property_data, "OPINION OF VALUE")

        # Date of report  
        pdf.set_font("Arial", '', 8)
        pdf.set_xy(130, 30)
        pdf.cell(70, 5, f"Effective Date of Value: 1/1/{property_data.get('tax_year', '2025')}", align='R')
        pdf.set_xy(130, 35)
        pdf.cell(70, 5, f"Date of Report: {today}", align='R')
        pdf.set_y(42)

        # Repeat owner info block (matching sample)
        pdf.set_fill_color(220, 225, 235)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(0, 7, "  Owner and Subject Property Information", ln=True, fill=True)
        pdf.set_font("Arial", '', 7)
        for r in rows[:3]:
            pdf.set_font("Arial", 'B', 7)
            pdf.cell(info_w[0], 6, r[0], 0)
            pdf.set_font("Arial", '', 7)
            pdf.cell(info_w[1], 6, r[1], 0)
            pdf.set_font("Arial", 'B', 7)
            pdf.cell(info_w[2], 6, r[2], 0)
            pdf.set_font("Arial", '', 7)
            pdf.cell(info_w[3], 6, r[3], 0)
            pdf.ln()

        pdf.ln(3)

        # Physical attributes (compact)
        for i, h in enumerate(pa_heads):
            pdf.set_font("Arial", 'B', 7)
            pdf.cell(pa_w[i], 7, h, 1, 0, 'C', True)
        pdf.ln()
        pdf.set_font("Arial", '', 7)
        for i, v in enumerate(pa_vals):
            pdf.cell(pa_w[i], 7, clean_text(str(v))[:14], 1, 0, 'C')
        pdf.ln()

        pdf.ln(5)

        # ── Value Assessment Summary ──
        equity_floor = self._parse_val(equity_data.get('justified_value_floor', appraised))

        # Calculate median sales value from sales_data
        median_sales = appraised
        if sales_data and len(sales_data) > 0:
            sale_prices = []
            for sc in sales_data:
                sp = self._parse_val(sc.get('Sale Price', 0) if isinstance(sc, dict) else getattr(sc, 'sale_price', 0))
                if sp > 0:
                    sale_prices.append(sp)
            if sale_prices:
                sale_prices.sort()
                median_sales = sale_prices[len(sale_prices) // 2]

        opinion_val = min(appraised, equity_floor, median_sales) if median_sales > 0 else min(appraised, equity_floor)

        pdf.set_fill_color(220, 225, 235)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(0, 7, "  Value Assessment Summary", ln=True, fill=True)

        val_w = [50, 30, 25, 25, 25, 25, 10]
        val_heads = ["Method", "Value", "PSF", "Land", "Impr.", "Change", ""]
        pdf.set_font("Arial", 'B', 7)
        for i, h in enumerate(val_heads):
            pdf.cell(val_w[i], 7, h, 1, 0, 'C', True)
        pdf.ln()

        # Improvement value = total - land
        subj_impr = max(0, appraised - subj_land)

        val_rows = [
            ("CAD Preliminary Market", self._fmt(market_val), self._pps(market_val, subj_area),
             self._fmt(subj_land), self._fmt(subj_impr), "", ""),
            ("Equity Uniformity (UE)", self._fmt(equity_floor), self._pps(equity_floor, subj_area),
             self._fmt(subj_land), self._fmt(max(0, equity_floor - subj_land)), "", ""),
            ("Sales Comparison", self._fmt(median_sales), self._pps(median_sales, subj_area),
             self._fmt(subj_land), self._fmt(max(0, median_sales - subj_land)), "", ""),
        ]
        pdf.set_font("Arial", '', 7)
        for row in val_rows:
            for i, v in enumerate(row):
                pdf.cell(val_w[i], 7, str(v), 1, 0, 'C' if i > 0 else 'L')
            pdf.ln()

        # Opinion of Value row (highlighted)
        pdf.set_fill_color(255, 230, 230)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(val_w[0], 10, "OPINION OF VALUE", 1, 0, 'L', True)
        pdf.cell(val_w[1], 10, self._fmt(opinion_val), 1, 0, 'C', True)
        pdf.set_font("Arial", '', 7)
        remaining_w = sum(val_w[2:])
        basis = "Market Sales" if opinion_val == median_sales else ("Equity Uniformity" if opinion_val == equity_floor else "CAD Market")
        pdf.cell(remaining_w, 10, f"  Opinion based on {basis} Approach.", 1, 1, 'L', True)

        pdf.ln(5)
        pdf.set_font("Arial", '', 8)
        pdf.multi_cell(0, 5, clean_text(
            "Based on a comprehensive review of Equity Uniformity (TC 41.43(b)(1)), "
            "Market Sales Comparables (TC 41.43(b)(3)), and Physical Condition (TC 23.01), "
            f"we propose the above opinion of value for tax year {property_data.get('tax_year', '2025')}."
        ))



        # (Equity grids and map moved to appendix — see end of document)

        # Pre-compute labels for use in both sales and equity grids
        subj_grade_disp = str(property_data.get('building_grade', 'N/A'))
        subj_year_built = str(property_data.get('year_built', ''))
        remodel_label = "New/Rebuilt" if property_data.get('year_built') and int(str(property_data.get('year_built'))[:4]) >= (datetime.datetime.now().year - 5) else str(property_data.get('year_built', ''))


        # ── SALES COMP GRIDS ═════════════════════════════════════════════════
        if sales_data and len(sales_data) > 0:
            # Paginate 3 comps per page
            sales_pages = []
            for i in range(0, min(len(sales_data), 6), 3):
                sales_pages.append(sales_data[i:i+3])

            for sp_idx, sp_comps in enumerate(sales_pages):
                pdf.add_page()
                self._draw_header(pdf, property_data, "RESIDENTIAL SALES COMP GRID")

                n_comps_s = len(sp_comps)
                factor_w = 32
                data_w = int((190 - factor_w) / max(1 + n_comps_s, 1))
                col_w = [factor_w] + [data_w] * (1 + n_comps_s)

                start_letter = sp_idx * 3
                headers = ["", "Subject"]
                for ci in range(len(sp_comps)):
                    headers.append(f"Comp {chr(65 + start_letter + ci)}")

                self._table_header(pdf, col_w, headers, (200, 230, 210))

                # Helper to get sales comp field (handles both dict and SalesComparable)
                def sc_get(sc, key, default='N/A'):
                    if isinstance(sc, dict):
                        return sc.get(key, default)
                    return getattr(sc, key, default)

                # Identity rows
                self._table_row(pdf, col_w, ["Prop ID", property_data.get('account_number', '')] +
                                [str(sc_get(sc, 'account_number', sc_get(sc, 'Prop ID', ''))) for sc in sp_comps])
                self._table_row(pdf, col_w, ["Neighborhood", str(nbhd)] +
                                [str(nbhd) for _ in sp_comps])
                self._table_row(pdf, col_w, ["Situs", clean_text(property_data.get('address', ''))[:25]] +
                                [clean_text(str(sc_get(sc, 'Address', sc_get(sc, 'address', ''))))[:25] for sc in sp_comps])

                # Value rows
                self._table_row(pdf, col_w, ["Year Built", str(property_data.get('year_built', ''))] +
                                [str(sc_get(sc, 'Year Built', sc_get(sc, 'year_built', ''))) for sc in sp_comps])
                self._table_row(pdf, col_w, ["Market Value", self._fmt(appraised)] +
                                [self._fmt(sc_get(sc, 'Sale Price', sc_get(sc, 'sale_price', 0))) for sc in sp_comps])

                sc_areas = []
                for sc in sp_comps:
                    a = self._parse_val(sc_get(sc, 'SqFt', sc_get(sc, 'sqft', 0)))
                    sc_areas.append(a)
                self._table_row(pdf, col_w, ["Total SQFT", f"{subj_area:,.0f} SF"] +
                                [f"{a:,.0f} SF" for a in sc_areas])

                sc_prices = [self._parse_val(sc_get(sc, 'Sale Price', sc_get(sc, 'sale_price', 0))) for sc in sp_comps]
                self._table_row(pdf, col_w, ["Market Price/SQFT", self._pps(appraised, subj_area)] +
                                [self._pps(p, a) if a > 0 else "N/A" for p, a in zip(sc_prices, sc_areas)])

                pdf.ln(2)

                # Sale-specific rows
                self._table_row(pdf, col_w, ["Sale Date", ""] +
                                [str(sc_get(sc, 'Sale Date', sc_get(sc, 'sale_date', '')))[:10] for sc in sp_comps])
                self._table_row(pdf, col_w, ["Sale Price", ""] +
                                [self._fmt(p) for p in sc_prices])

                pdf.ln(2)

                # Adjustment rows (simplified for sales — compute basic adjustments)
                from backend.services.valuation_service import valuation_service
                for sc_i, sc in enumerate(sp_comps):
                    # Build a normalized comp dict for valuation_service (maps API keys → internal keys)
                    sc_normalized = {
                        'building_area': sc_areas[sc_i] or self._parse_val(sc_get(sc, 'SqFt', sc_get(sc, 'sqft', 0))),
                        'appraised_value': sc_prices[sc_i] or self._parse_val(sc_get(sc, 'Sale Price', sc_get(sc, 'sale_price', 0))),
                        'year_built': sc_get(sc, 'Year Built', sc_get(sc, 'year_built', '')),
                        'building_grade': sc_get(sc, 'Grade', sc_get(sc, 'building_grade', property_data.get('building_grade', 'B-'))),
                        'land_value': self._parse_val(sc_get(sc, 'land_value', 0)),
                        'neighborhood_code': sc_get(sc, 'neighborhood_code', nbhd),
                    }
                    if 'adjustments' not in (sc if isinstance(sc, dict) else {}):
                        adj = valuation_service.calculate_adjustments(property_data, sc_normalized)
                        if isinstance(sc, dict):
                            sc['adjustments'] = adj
                        else:
                            sc.adjustments = adj

                # Adjustment detail rows
                self._table_row(pdf, col_w, ["Year Remodeled", str(property_data.get('year_built', ''))] +
                                [str(sc_get(sc, 'Year Built', sc_get(sc, 'year_built', ''))) for sc in sp_comps])
                self._table_row(pdf, col_w, ["Remodel Adj", remodel_label] +
                                ["$0" for _ in sp_comps])
                self._table_row(pdf, col_w, ["Grade Adj", subj_grade_disp] +
                                [self._fmt((sc.get('adjustments', {}) if isinstance(sc, dict) else getattr(sc, 'adjustments', {})).get('grade', 0)) for sc in sp_comps])
                self._table_row(pdf, col_w, ["Size Index Adj", ""] +
                                [self._fmt((sc.get('adjustments', {}) if isinstance(sc, dict) else getattr(sc, 'adjustments', {})).get('size', 0)) for sc in sp_comps])
                subj_pct = 97
                if comps:
                    subj_pct = comps[0].get('adjustments', {}).get('subject_pct_good', 97)
                elif sp_comps:
                    adj = (sp_comps[0].get('adjustments', {}) if isinstance(sp_comps[0], dict) else getattr(sp_comps[0], 'adjustments', {}))
                    subj_pct = adj.get('subject_pct_good', 97)
                self._table_row(pdf, col_w, ["% Good Adj", f"{subj_pct}%"] +
                                [f"{(sc.get('adjustments', {}) if isinstance(sc, dict) else getattr(sc, 'adjustments', {})).get('comp_pct_good', 80)}%" for sc in sp_comps])

                pdf.ln(2)

                self._table_row(pdf, col_w, ["Land Value Adj", self._fmt(subj_land)] +
                                [self._fmt((sc.get('adjustments', {}) if isinstance(sc, dict) else getattr(sc, 'adjustments', {})).get('land_value', 0)) for sc in sp_comps])
                self._table_row(pdf, col_w, ["Segments & Adj", "$0"] + ["$0" for _ in sp_comps])
                self._table_row(pdf, col_w, ["Other Improvements", "$0"] + ["$0" for _ in sp_comps])

                pdf.ln(2)

                # Net Adjustment
                pdf.set_fill_color(230, 240, 255)
                pdf.set_font("Arial", 'B', 7)
                net_vals = ["Net Adjustment", ""]
                for sc in sp_comps:
                    adj = (sc.get('adjustments', {}) if isinstance(sc, dict) else getattr(sc, 'adjustments', {}))
                    net_vals.append(self._fmt(adj.get('net_adjustment', 0)))
                for i, v in enumerate(net_vals):
                    pdf.cell(col_w[i], 8, clean_text(str(v)), 1, 0, 'C' if i > 0 else 'L', True)
                pdf.ln()

                pdf.ln(1)

                # Indicated Value
                ind_vals = ["Indicated Value", ""]
                for sc in sp_comps:
                    adj = (sc.get('adjustments', {}) if isinstance(sc, dict) else getattr(sc, 'adjustments', {}))
                    ind_vals.append(self._fmt(adj.get('indicated_value', 0)))
                pdf.set_fill_color(220, 255, 220)
                for i, v in enumerate(ind_vals):
                    pdf.cell(col_w[i], 8, clean_text(str(v)), 1, 0, 'C' if i > 0 else 'L', True)
                pdf.ln()

                pdf.ln(3)

                # Median Sales Summary
                pdf.set_font("Arial", 'B', 8)
                pdf.cell(90, 8, f"Median Sales Value: {self._fmt(median_sales)}", 0, 0, 'L')
                pdf.cell(90, 8, f"Median Sales Value / SQFT: {self._pps(median_sales, subj_area)}", 0, 1, 'R')

            # ── SALES MAP PAGE ────────────────────────────────────────────────
            pdf.add_page()
            self._draw_header(pdf, property_data, "SALES GEOGRAPHIC CONTEXT")
            s_addrs = []
            for sc in sales_data[:7]:
                a = sc.get('Address', sc.get('address', '')) if isinstance(sc, dict) else getattr(sc, 'address', '')
                if a: s_addrs.append(a)
            if s_addrs:
                map_s = self._generate_static_map(property_data.get('address'), s_addrs, "green")
                if map_s:
                    pdf.image(map_s, x=10, y=40, w=190)
                    try: os.unlink(map_s)
                    except: pass
                else:
                    pdf.set_font("Arial", '', 10)
                    pdf.ln(20)
                    pdf.cell(0, 10, "Map: Google Maps API key required for geographic context.", ln=True, align='C')

            pdf.set_y(200)
            pdf.set_font("Arial", 'B', 8)
            pdf.cell(0, 6, f"Owner Name: {clean_text(owner_name)}  |  Address: {clean_text(property_data.get('address', ''))}", ln=True)
            pdf.cell(0, 6, f"Account Number: {property_data.get('account_number', '')}  |  {clean_text(property_data.get('address', ''))}", ln=True)

        # ══════════════════════════════════════════════════════════════════════════
        # ██  ENHANCEMENT PAGES — AI-POWERED DIFFERENTIATORS
        # ══════════════════════════════════════════════════════════════════════════

        # ── EXECUTIVE SUMMARY DASHBOARD (Enhancement #9) ═══════════════════════
        pdf.add_page()
        self._draw_header(pdf, property_data, "EXECUTIVE SUMMARY & PROTEST SCORECARD")

        # ─── Protest Strength Score (Enhancement #3) ──────────────────────
        # Calculate protest strength based on available evidence
        equity_gap = max(0, appraised - equity_floor) if equity_floor > 0 else 0
        sales_gap = max(0, appraised - median_sales) if median_sales > 0 else 0
        condition_deduction = sum(i.get('deduction', 0) for i in (vision_data or []) if isinstance(i, dict)) if vision_data else 0
        flood_zone = property_data.get('flood_zone', 'Zone X')
        has_flood = flood_zone and 'Zone X' not in str(flood_zone)
        permit_info = permit_data or property_data.get('permit_summary', {})
        has_no_permits = not (permit_info.get('has_renovations', False)) if permit_info else True

        # Score components (0-100)
        score_equity = min(40, int((equity_gap / max(appraised, 1)) * 200)) if equity_gap > 0 else 0
        score_sales = min(25, int((sales_gap / max(appraised, 1)) * 125)) if sales_gap > 0 else 0
        score_condition = min(15, int(condition_deduction / 1000)) if condition_deduction > 0 else 0
        score_flood = 10 if has_flood else 0
        score_permits = 10 if has_no_permits else 0
        total_score = min(100, score_equity + score_sales + score_condition + score_flood + score_permits)

        # Win probability mapping
        if total_score >= 70: win_prob, win_label, win_color = "85-95%", "STRONG", (34, 197, 94)
        elif total_score >= 45: win_prob, win_label, win_color = "60-80%", "GOOD", (59, 130, 246)
        elif total_score >= 25: win_prob, win_label, win_color = "35-55%", "MODERATE", (251, 191, 36)
        else: win_prob, win_label, win_color = "15-30%", "WEAK", (239, 68, 68)

        # Large scorecard box
        pdf.set_fill_color(*win_color)
        pdf.rect(15, 35, 180, 40, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(20, 38)
        pdf.set_font("Arial", 'B', 28)
        pdf.cell(80, 15, f"Score: {total_score}/100")
        pdf.set_font("Arial", 'B', 20)
        pdf.cell(90, 15, f"Win Probability: {win_prob}", align='R')
        pdf.set_xy(20, 55)
        pdf.set_font("Arial", '', 14)
        pdf.cell(170, 12, f"Protest Strength: {win_label} | Estimated Savings: {self._fmt(max(equity_gap, sales_gap))} - {self._fmt(max(equity_gap, sales_gap) + condition_deduction)}", align='C')
        pdf.set_text_color(0, 0, 0)

        pdf.set_y(82)

        # Method indicators with traffic lights
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(0, 8, "Evidence Quality by Method", ln=True)

        methods = [
            ("Equity Uniformity (TC 41.43(b)(1))", score_equity, 40,
             f"Gap: {self._fmt(equity_gap)} | {len(comps)} comps analyzed"),
            ("Sales Comparison (TC 41.43(b)(3))", score_sales, 25,
             f"Gap: {self._fmt(sales_gap)} | {len(sales_data or [])} sales comps"),
            ("Physical Condition (TC 23.01)", score_condition, 15,
             f"Deductions: {self._fmt(condition_deduction)} | {len([i for i in (vision_data or []) if isinstance(i, dict) and i.get('issue') != 'CONDITION_SUMMARY'])} issues"),
            ("Environmental Factors (Flood/FEMA)", score_flood, 10,
             f"Zone: {flood_zone} | {'High Risk' if has_flood else 'Minimal Risk'}"),
            ("Deferred Maintenance (Permits)", score_permits, 10,
             f"{'No major renovations on record' if has_no_permits else 'Recent renovations detected'}"),
        ]

        for method_name, score, max_score, detail in methods:
            # Traffic light
            if score >= max_score * 0.6: light = (34, 197, 94)  # Green
            elif score >= max_score * 0.3: light = (251, 191, 36)  # Yellow
            elif score > 0: light = (239, 68, 68)  # Red
            else: light = (180, 180, 180)  # Gray

            y = pdf.get_y()
            pdf.set_fill_color(*light)
            pdf.ellipse(15, y + 1.5, 5, 5, 'F')
            pdf.set_xy(23, y)
            pdf.set_font("Arial", 'B', 8)
            pdf.cell(60, 7, clean_text(method_name))
            pdf.set_font("Arial", '', 8)
            pdf.cell(25, 7, f"{score}/{max_score} pts", align='C')

            # Mini progress bar
            bar_x = 110
            bar_w = 80
            bar_h = 4
            pdf.set_fill_color(230, 230, 230)
            pdf.rect(bar_x, y + 1.5, bar_w, bar_h, 'F')
            filled_w = (score / max(max_score, 1)) * bar_w
            pdf.set_fill_color(*light)
            pdf.rect(bar_x, y + 1.5, filled_w, bar_h, 'F')
            pdf.ln(9)

            # Detail line
            pdf.set_xy(23, pdf.get_y() - 2)
            pdf.set_font("Arial", '', 7)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, clean_text(detail), ln=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)

        pdf.ln(5)

        # Value comparison summary box
        pdf.ln(3)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 7, "Value Comparison at a Glance", ln=True)

        bar_data = [
            ("District Value", appraised, (239, 68, 68)),
            ("Equity Value", equity_floor, (59, 130, 246)),
            ("Sales Value", median_sales, (34, 197, 94)),
            ("Opinion of Value", opinion_val, (147, 51, 234)),
        ]
        max_bar_val = max(v for _, v, _ in bar_data) if bar_data else 1
        for label, val, color in bar_data:
            y = pdf.get_y()
            pdf.set_font("Arial", '', 7)
            pdf.cell(30, 5, label)
            bar_x = 52
            bar_max_w = 100
            bar_w = (val / max(max_bar_val, 1)) * bar_max_w
            pdf.set_fill_color(230, 230, 230)
            pdf.rect(bar_x, y + 0.5, bar_max_w, 4, 'F')
            pdf.set_fill_color(*color)
            pdf.rect(bar_x, y + 0.5, bar_w, 4, 'F')
            pdf.set_xy(bar_x + bar_max_w + 2, y)
            pdf.set_font("Arial", 'B', 7)
            pdf.cell(30, 5, self._fmt(val))
            pdf.ln()

        # ── VALUATION TREND & FORECAST (Enhancement #4) ═══════════════════
        history = property_data.get('valuation_history', {})
        if history and len(history) >= 2:
            pdf.add_page()
            self._draw_header(pdf, property_data, "VALUATION TREND & FORECAST ANALYSIS")

            sorted_years = sorted(history.keys())
            values_by_year = []
            for yr in sorted_years:
                v = history[yr]
                mkt = self._parse_val(v.get('market', 0))
                appr_v = self._parse_val(v.get('appraised', 0))
                values_by_year.append((yr, mkt, appr_v))

            # Draw simple bar chart using rectangles
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(0, 10, "Assessment History & Growth Rate", ln=True)

            chart_x = 30
            chart_y = pdf.get_y() + 5
            chart_w = 150
            chart_h = 80
            max_val = max(max(m, a) for _, m, a in values_by_year) if values_by_year else 1
            n_years = len(values_by_year)
            bar_group_w = chart_w / max(n_years, 1)
            bar_w = bar_group_w * 0.35

            # Y-axis labels
            for i in range(5):
                y_pos = chart_y + chart_h - (i / 4) * chart_h
                val_label = self._fmt(max_val * i / 4)
                pdf.set_font("Arial", '', 6)
                pdf.set_xy(5, y_pos - 2)
                pdf.cell(24, 4, val_label, align='R')
                # Grid line
                pdf.set_draw_color(230, 230, 230)
                pdf.line(chart_x, y_pos, chart_x + chart_w, y_pos)

            # Bars
            for idx, (yr, mkt, appr_v) in enumerate(values_by_year):
                x = chart_x + idx * bar_group_w + bar_group_w * 0.15
                # Market bar
                h_mkt = (mkt / max(max_val, 1)) * chart_h
                pdf.set_fill_color(59, 130, 246)
                pdf.rect(x, chart_y + chart_h - h_mkt, bar_w, h_mkt, 'F')
                # Appraised bar
                h_appr = (appr_v / max(max_val, 1)) * chart_h
                pdf.set_fill_color(34, 197, 94)
                pdf.rect(x + bar_w + 1, chart_y + chart_h - h_appr, bar_w, h_appr, 'F')
                # Year label
                pdf.set_font("Arial", '', 7)
                pdf.set_xy(x, chart_y + chart_h + 2)
                pdf.cell(bar_group_w * 0.7, 5, str(yr), align='C')

            pdf.set_draw_color(0, 0, 0)

            # Legend
            pdf.set_y(chart_y + chart_h + 12)
            pdf.set_fill_color(59, 130, 246)
            pdf.rect(chart_x, pdf.get_y(), 8, 4, 'F')
            pdf.set_xy(chart_x + 10, pdf.get_y())
            pdf.set_font("Arial", '', 8)
            pdf.cell(30, 5, "Market Value")
            pdf.set_fill_color(34, 197, 94)
            pdf.rect(chart_x + 45, pdf.get_y(), 8, 4, 'F')
            pdf.set_xy(chart_x + 55, pdf.get_y())
            pdf.cell(30, 5, "Appraised Value")
            pdf.ln(10)

            # Growth rate table
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(0, 8, "Year-over-Year Growth Analysis", ln=True)
            grow_w = [25, 30, 30, 25, 25, 30, 25]
            grow_heads = ["Year", "Market Val", "Appraised", "Change $", "Change %", "PSF", "Cap Applied"]
            self._table_header(pdf, grow_w, grow_heads)

            prev_mkt = None
            for yr, mkt, appr_v in values_by_year:
                change_d = ""
                change_p = ""
                if prev_mkt and prev_mkt > 0:
                    d = mkt - prev_mkt
                    p = (d / prev_mkt) * 100
                    change_d = f"+{self._fmt(d)}" if d >= 0 else self._fmt(d)
                    change_p = f"{p:+.1f}%"
                prev_mkt = mkt
                psf = f"${mkt/subj_area:,.2f}" if mkt > 0 and subj_area > 1 else "---"
                cap = "Yes" if appr_v != mkt and appr_v > 0 and mkt > 0 else "No"
                self._table_row(pdf, grow_w, [yr, self._fmt(mkt), self._fmt(appr_v), change_d, change_p, psf, cap])

            pdf.ln(5)

            # Forecast projection
            if len(values_by_year) >= 2:
                last_mkt = values_by_year[-1][1]
                prev_mkt_val = values_by_year[-2][1]
                if prev_mkt_val > 0 and last_mkt > 0:
                    growth_rate = (last_mkt - prev_mkt_val) / prev_mkt_val
                    proj_next = last_mkt * (1 + growth_rate)
                    proj_2yr = proj_next * (1 + growth_rate)

                    pdf.set_fill_color(255, 248, 220)
                    pdf.rect(15, pdf.get_y(), 180, 25, 'F')
                    pdf.set_xy(20, pdf.get_y() + 3)
                    pdf.set_font("Arial", 'B', 9)
                    pdf.cell(0, 6, "AI Forecast (Based on Current Trend)", ln=True)
                    pdf.set_x(20)
                    pdf.set_font("Arial", '', 8)
                    pdf.cell(0, 5, clean_text(
                        f"At the current {growth_rate*100:.1f}% annual growth rate, your assessment could reach "
                        f"{self._fmt(proj_next)} next year and {self._fmt(proj_2yr)} in two years. "
                        f"A successful protest now prevents compounding over-assessment."
                    ), ln=True)

        # ── AI COMP PHOTO COMPARISON (Enhancement #1) ═════════════════════
        if comp_images and len(comp_images) > 0:
            pdf.add_page()
            self._draw_header(pdf, property_data, "AI PROPERTY CONDITION COMPARISON")

            pdf.set_font("Arial", '', 8)
            pdf.multi_cell(0, 5, clean_text(
                "Street-level imagery was analyzed by AI to compare the physical condition of the subject "
                "property against each comparable. Condition differences support adjustment arguments "
                "under Texas Tax Code Sec. 23.01 (market value considers physical condition)."
            ))
            pdf.ln(3)

            # Subject property image
            subj_img = comp_images.get('subject')
            subj_img_bottom = pdf.get_y()
            if subj_img and os.path.exists(subj_img):
                pdf.set_fill_color(220, 225, 235)
                pdf.set_font("Arial", 'B', 8)
                pdf.cell(0, 7, f"  SUBJECT: {clean_text(property_data.get('address', ''))}", ln=True, fill=True)
                img_top_y = pdf.get_y()
                try:
                    pdf.image(subj_img, x=10, y=img_top_y, w=90, h=55)
                except: pass
                pdf.set_xy(105, img_top_y)
                pdf.set_font("Arial", '', 8)
                subj_condition = comp_images.get('subject_condition', 'Good condition - No major defects detected')
                subj_text = clean_text(f"AI Assessment: {subj_condition}")
                if len(subj_text) > 320:
                    subj_text = subj_text[:317] + "..."
                pdf.multi_cell(95, 5, subj_text)
                # Ensure Y is past the image (image is 55mm tall)
                subj_img_bottom = img_top_y + 55 + 5
                pdf.set_y(max(pdf.get_y(), subj_img_bottom))

            # Comp images (2 per row)
            comp_entries = [(k, v) for k, v in comp_images.items()
                          if k not in ('subject', 'subject_condition') and not k.endswith('_condition')]
            # Start position for comps - ensure clean start after subject
            pdf.ln(3)
            row_height = 80  # Header(6) + image(50) + text(~22) + margin(2)
            row_start_y = pdf.get_y()  # Anchor for current row

            for ci, (comp_key, img_path) in enumerate(comp_entries[:6]):
                if not os.path.exists(img_path):
                    continue

                # Extract condition text
                condition_text = comp_images.get(f"{comp_key}_condition", "Condition assessment unavailable.")

                col = ci % 2

                # At the start of each new row (left column), anchor the row Y
                if col == 0:
                    if ci > 0:
                        row_start_y = row_start_y + row_height
                    # Page break check
                    if row_start_y + row_height > 255:
                        pdf.add_page()
                        self._draw_header(pdf, property_data, "AI PROPERTY CONDITION COMPARISON (cont.)")
                        row_start_y = 35

                # X position based on column; Y always equals row_start_y
                x_offset = 15 if col == 0 else 110
                current_y = row_start_y

                # 1. Header Box
                pdf.set_fill_color(220, 225, 235)
                pdf.set_font("Arial", 'B', 7)
                pdf.set_xy(x_offset, current_y)
                pdf.cell(90, 6, clean_text(f"COMP {chr(65 + ci)}: {comp_key}")[:50], fill=True)
                pdf.set_fill_color(255, 255, 255)  # Reset after fill

                # 2. Image — placed at fixed offset below header
                try:
                    pdf.image(img_path, x=x_offset, y=current_y + 7, w=90, h=50)
                except:
                    pass

                # 3. Condition text — placed below image with proper spacing
                pdf.set_xy(x_offset, current_y + 58)
                pdf.set_font("Arial", '', 6.5)
                raw_assessment = clean_text(f"AI Assessment: {condition_text}")
                if len(raw_assessment) > 130:
                    raw_assessment = raw_assessment[:127] + "..."
                pdf.multi_cell(90, 3.5, raw_assessment)

            # Move past the last row
            pdf.set_y(row_start_y + row_height + 5)
        elif image_paths and len(image_paths) > 0:
            # Fallback: just show subject images without comp comparison
            pass

        # ── FEMA FLOOD ZONE & ENVIRONMENTAL RISK (Enhancement #5) ═════════
        flood_info = flood_data or {}
        if not flood_info:
            # Try to get from property_data
            fz = property_data.get('flood_zone', '')
            if fz:
                flood_info = {'zone': fz, 'is_high_risk': 'Zone X' not in str(fz)}

        if flood_info:
            pdf.add_page()
            self._draw_header(pdf, property_data, "ENVIRONMENTAL & FLOOD RISK ANALYSIS")

            fz_zone = flood_info.get('zone', 'Zone X')
            fz_high = flood_info.get('is_high_risk', False)

            # Risk indicator box
            if fz_high:
                pdf.set_fill_color(254, 226, 226)
                risk_text = "HIGH RISK"
                risk_detail = "This property is located in a FEMA Special Flood Hazard Area (SFHA)."
            else:
                pdf.set_fill_color(220, 252, 231)
                risk_text = "LOW RISK"
                risk_detail = "This property is located outside FEMA Special Flood Hazard Areas."

            pdf.rect(15, 35, 180, 30, 'F')
            pdf.set_xy(20, 38)
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(80, 10, f"Flood Zone: {fz_zone}")
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(90, 10, risk_text, align='R')
            pdf.set_xy(20, 52)
            pdf.set_font("Arial", '', 9)
            pdf.cell(170, 6, clean_text(risk_detail))

            pdf.set_y(72)

            # Flood zone explanation table
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(0, 8, "FEMA Flood Zone Classification", ln=True)
            fz_w = [25, 55, 110]
            fz_heads = ["Zone", "Risk Level", "Impact on Property Value"]
            self._table_header(pdf, fz_w, fz_heads)
            zones = [
                ("A / AE", "High (100-yr)", "Mandatory flood insurance, 15-25% value reduction, limited financing options"),
                ("AH / AO", "High (Shallow)", "Flood insurance required, 10-20% value impact, ponding/sheet flow risk"),
                ("V / VE", "Very High", "Coastal flooding, 20-35% value impact, strictest building codes"),
                ("X (shaded)", "Moderate", "500-year flood risk, optional insurance, 0-5% value impact"),
                ("X", "Minimal", "Outside flood zones, no insurance requirement, no value impact"),
            ]
            for z, risk, impact in zones:
                is_current = fz_zone in z or z.startswith(fz_zone)
                if is_current:
                    pdf.set_fill_color(255, 255, 200)
                else:
                    pdf.set_fill_color(255, 255, 255)
                pdf.set_font("Arial", 'B' if is_current else '', 7)
                pdf.cell(fz_w[0], 7, z, 1, 0, 'C', is_current)
                pdf.cell(fz_w[1], 7, risk, 1, 0, 'C', is_current)
                pdf.set_font("Arial", '', 7)
                pdf.cell(fz_w[2], 7, impact[:60], 1, 1, 'L', is_current)

            pdf.ln(5)

            # Valuation impact
            if fz_high:
                flood_adj_pct = 0.05  # 5% deduction
                flood_adj_val = appraised * flood_adj_pct
                pdf.set_fill_color(254, 243, 199)
                pdf.rect(15, pdf.get_y(), 180, 25, 'F')
                pdf.set_xy(20, pdf.get_y() + 3)
                pdf.set_font("Arial", 'B', 9)
                pdf.cell(0, 6, "External Obsolescence Deduction", ln=True)
                pdf.set_x(20)
                pdf.set_font("Arial", '', 8)
                pdf.multi_cell(165, 5, clean_text(
                    f"Properties in FEMA Zone {fz_zone} typically sell at a 5-15% discount compared to "
                    f"Zone X properties. A conservative 5% deduction yields {self._fmt(flood_adj_val)} in "
                    f"external obsolescence, reducing the indicated value to {self._fmt(appraised - flood_adj_val)}. "
                    f"This deduction is supported by paired sales analysis methodology."
                ))
            else:
                pdf.set_font("Arial", '', 9)
                pdf.multi_cell(0, 6, clean_text(
                    f"The subject property is in FEMA Zone {fz_zone}, which has minimal flood risk. "
                    f"No external obsolescence deduction is applicable from flood exposure. However, "
                    f"regional flood events may still impact neighborhood desirability and market perception."
                ))

        # ── PERMIT & RENOVATION CROSS-REFERENCE (Enhancement #6) ═════════
        permit_info_full = permit_data or property_data.get('permit_summary', {})
        comp_renos = comp_renovations or []

        if permit_info_full or comp_renos:
            pdf.add_page()
            self._draw_header(pdf, property_data, "PERMIT & RENOVATION ANALYSIS")

            # Subject property permits
            pdf.set_fill_color(220, 225, 235)
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(0, 7, "  Subject Property Permit History", ln=True, fill=True)

            has_renos = permit_info_full.get('has_renovations', False) if permit_info_full else False
            major_permits = permit_info_full.get('major_permits', []) if permit_info_full else []

            if major_permits:
                perm_w = [35, 90, 30, 35]
                perm_heads = ["Date", "Description", "Value", "Impact"]
                self._table_header(pdf, perm_w, perm_heads)
                for p in major_permits:
                    pdf.set_font("Arial", '', 7)
                    pdf.cell(perm_w[0], 7, str(p.get('date', 'N/A'))[:12], 1)
                    pdf.cell(perm_w[1], 7, clean_text(str(p.get('description', '')))[:45], 1)
                    pdf.cell(perm_w[2], 7, self._fmt(p.get('value', 0)), 1, 0, 'R')
                    pdf.cell(perm_w[3], 7, "Upgrade" if float(p.get('value', 0) or 0) > 25000 else "Minor", 1, 1, 'C')
            else:
                pdf.set_font("Arial", '', 8)
                pdf.set_fill_color(220, 252, 231)
                pdf.cell(0, 10, "  No major renovation permits found. This supports a deferred-maintenance argument.", ln=True, fill=True)

            pdf.ln(5)

            # Argument callout
            if not has_renos:
                pdf.set_fill_color(239, 246, 255)
                pdf.set_font("Arial", 'B', 8)
                pdf.cell(0, 7, "  Deferred Maintenance Argument (TC 23.01)", ln=True, fill=True)
                pdf.set_font("Arial", '', 7)
                pdf.multi_cell(0, 4, clean_text(
                    "City permit records show no major renovations or improvements filed for this property. "
                    "The absence of documented upgrades, combined with the property's age, supports a "
                    "deferred-maintenance depreciation model. The district's valuation may not adequately "
                    "account for the property's actual physical condition."
                ))
                pdf.ln(3)

            # Comparable permit analysis
            if comp_renos:
                pdf.set_fill_color(220, 225, 235)
                pdf.set_font("Arial", 'B', 9)
                pdf.cell(0, 7, "  Comparable Properties — Documented Renovations", ln=True, fill=True)

                for reno in comp_renos:
                    pdf.set_font("Arial", 'B', 8)
                    pdf.cell(0, 7, f"  {clean_text(reno.get('address', 'Unknown'))}", ln=True)
                    for permit in reno.get('renovations', []):
                        pdf.set_font("Arial", '', 7)
                        pdf.cell(10, 5, "")
                        pdf.cell(35, 5, str(permit.get('date', ''))[:12])
                        pdf.cell(100, 5, clean_text(str(permit.get('description', '')))[:55])
                        pdf.cell(25, 5, self._fmt(permit.get('value', 0)), align='R')
                        pdf.ln()
                    pdf.set_font("Arial", 'I', 7)
                    pdf.set_text_color(100, 100, 100)
                    pdf.cell(0, 5, f"    {clean_text(reno.get('adjustment_logic', ''))}", ln=True)
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln(2)

        # ── NEIGHBORHOOD MARKET ANALYSIS (Enhancement #7) ═════════════════
        if sales_data and len(sales_data) > 0:
            pdf.add_page()
            self._draw_header(pdf, property_data, "NEIGHBORHOOD MARKET ANALYSIS")

            pdf.set_font("Arial", '', 8)
            pdf.multi_cell(0, 5, clean_text(
                "This analysis examines recent market activity in the subject property's neighborhood "
                "to assess whether the district's valuation aligns with actual market conditions. "
                "A sale-to-assessment ratio below 1.0 indicates systematic over-assessment in the area."
            ))
            pdf.ln(3)

            # Calculate market metrics from sales data
            sale_prices_all = []
            sale_areas_all = []
            for sc in sales_data:
                if isinstance(sc, dict):
                    sp = self._parse_val(sc.get('Sale Price', sc.get('sale_price', 0)))
                    sa = self._parse_val(sc.get('SqFt', sc.get('sqft', 0)))
                else:
                    sp = self._parse_val(getattr(sc, 'sale_price', 0))
                    sa = self._parse_val(getattr(sc, 'sqft', 0))
                if sp > 0: sale_prices_all.append(sp)
                if sa > 0: sale_areas_all.append(sa)

            if sale_prices_all:
                sale_prices_all.sort()
                median_sp = sale_prices_all[len(sale_prices_all) // 2]
                avg_sp = sum(sale_prices_all) / len(sale_prices_all)
                min_sp = min(sale_prices_all)
                max_sp = max(sale_prices_all)

                avg_pps = sum(sale_prices_all) / sum(sale_areas_all) if sale_areas_all else 0
                sar = median_sp / appraised if appraised > 0 else 0

                # Key metrics boxes
                metrics = [
                    ("Median Sale", self._fmt(median_sp), (59, 130, 246)),
                    ("Average Sale", self._fmt(avg_sp), (34, 197, 94)),
                    ("Avg $/SqFt", f"${avg_pps:,.2f}" if avg_pps else "N/A", (147, 51, 234)),
                    ("Sale/Assess Ratio", f"{sar:.2f}", (239, 68, 68) if sar < 1.0 else (34, 197, 94)),
                ]

                box_w = 42
                box_row_y = pdf.get_y()  # Anchor Y BEFORE the loop to prevent staircase
                for i, (label, val, color) in enumerate(metrics):
                    x = 15 + i * (box_w + 4)
                    y = box_row_y  # All boxes start at the same Y
                    pdf.set_fill_color(*color)
                    pdf.rect(x, y, box_w, 22, 'F')
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_xy(x + 2, y + 2)
                    pdf.set_font("Arial", '', 7)
                    pdf.cell(box_w - 4, 5, label, align='C')
                    pdf.set_xy(x + 2, y + 9)
                    pdf.set_font("Arial", 'B', 11)
                    pdf.cell(box_w - 4, 10, str(val), align='C')

                pdf.set_text_color(0, 0, 0)
                pdf.set_fill_color(255, 255, 255)
                pdf.set_y(box_row_y + 28)

                # Sales detail table
                pdf.set_font("Arial", 'B', 9)
                pdf.cell(0, 8, "Recent Neighborhood Sales Activity", ln=True)
                st_w = [55, 25, 25, 20, 20, 22, 23]
                st_heads = ["Address", "Sale Price", "$/SqFt", "SqFt", "Year", "Date", "Ratio"]
                self._table_header(pdf, st_w, st_heads)

                for sc in sales_data[:8]:
                    if isinstance(sc, dict):
                        addr = sc.get('Address', sc.get('address', ''))
                        sp = self._parse_val(sc.get('Sale Price', sc.get('sale_price', 0)))
                        sa = self._parse_val(sc.get('SqFt', sc.get('sqft', 0)))
                        yr = sc.get('Year Built', sc.get('year_built', ''))
                        dt = sc.get('Sale Date', sc.get('sale_date', ''))
                        pps = sp / sa if sa > 0 else 0
                    else:
                        addr = getattr(sc, 'address', '')
                        sp = self._parse_val(getattr(sc, 'sale_price', 0))
                        sa = self._parse_val(getattr(sc, 'sqft', 0))
                        yr = getattr(sc, 'year_built', '')
                        dt = getattr(sc, 'sale_date', '')
                        pps = sp / sa if sa > 0 else 0

                    ratio_val = sp / appraised if appraised > 0 and sp > 0 else 0
                    self._table_row(pdf, st_w, [
                        clean_text(str(addr))[:28], self._fmt(sp), f"${pps:,.2f}",
                        f"{sa:,.0f}", str(yr), str(dt)[:10], f"{ratio_val:.2f}"
                    ])

                pdf.ln(5)

                # Market analysis callout
                if sar < 1.0:
                    pdf.set_fill_color(254, 243, 199)
                    pdf.rect(15, pdf.get_y(), 180, 20, 'F')
                    pdf.set_xy(20, pdf.get_y() + 3)
                    pdf.set_font("Arial", 'B', 9)
                    pdf.cell(0, 6, "Market Over-Assessment Indicator", ln=True)
                    pdf.set_x(20)
                    pdf.set_font("Arial", '', 8)
                    pdf.multi_cell(165, 4, clean_text(
                        f"The median sale-to-assessment ratio of {sar:.2f} indicates that comparable properties "
                        f"are selling below their assessed values. This systematic over-assessment pattern suggests "
                        f"the district's valuations exceed actual market conditions by approximately "
                        f"{self._fmt(appraised - median_sp)} ({(1 - sar) * 100:.1f}%)."
                    ))

        # ══════════════════════════════════════════════════════════════════════════
        # ██  COST APPROACH VALIDATION (Enhancement #8)
        # ══════════════════════════════════════════════════════════════════════════
        pdf.add_page()
        self._draw_header(pdf, property_data, "COST APPROACH VALIDATION")

        year_built = int(str(property_data.get('year_built', 0))[:4]) if property_data.get('year_built') else 0
        current_year = datetime.datetime.now().year
        actual_age = max(0, current_year - year_built) if year_built > 1900 else 0
        sqft = self._parse_val(property_data.get('building_area', 0))
        grade = str(property_data.get('building_grade', 'C')).upper().strip()
        land_val = self._parse_val(property_data.get('land_value', subj_land))

        # Cost-per-sqft by grade (Marshall & Swift residential approximation)
        grade_costs = {
            'A+': 225, 'A': 200, 'A-': 185, 'B+': 170, 'B': 155, 'B-': 140,
            'C+': 128, 'C': 115, 'C-': 105, 'D+': 95, 'D': 85, 'D-': 75
        }
        cost_psf = grade_costs.get(grade, 115)
        replacement_cost_new = sqft * cost_psf

        # Depreciation calculation
        economic_life = 55  # Typical Texas residential
        effective_age = actual_age  # Adjusted below if condition data available
        cond_summary = [v for v in (vision_data or []) if isinstance(v, dict) and v.get('issue') == 'CONDITION_SUMMARY']
        if cond_summary:
            ea = cond_summary[0].get('effective_age')
            if ea and int(str(ea).split('.')[0]) > 0:
                effective_age = int(str(ea).split('.')[0])
        effective_age = min(effective_age, economic_life)  # Cap at economic life

        physical_depr_pct = min(effective_age / economic_life, 0.90)  # Max 90%
        physical_depr_amt = replacement_cost_new * physical_depr_pct
        functional_obs = 0  # Could be from vision data
        external_obs = 0    # Could be from flood data
        if flood_data and flood_data.get('is_high_risk'):
            external_obs = replacement_cost_new * 0.05  # 5% for high-risk flood zone
        total_depreciation = physical_depr_amt + functional_obs + external_obs
        depreciated_value = replacement_cost_new - total_depreciation
        cost_approach_value = land_val + depreciated_value

        pdf.set_font("Arial", '', 9)
        pdf.multi_cell(0, 5, clean_text(
            "The Cost Approach estimates value by calculating the cost to replace the improvement "
            "as new, deducting accrued depreciation, and adding land value. This method serves as an "
            "independent check on market-derived approaches per Texas Tax Code Sec. 23.011 and provides "
            "a ceiling on reasonable value when physical deterioration is present."
        ))
        pdf.ln(3)

        # Replacement Cost table
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, "Replacement Cost New (RCN)", ln=True)
        ca_w = [95, 95]
        self._table_header(pdf, ca_w, ["Component", "Value"])
        rows = [
            ("Building Area", f"{sqft:,.0f} sqft"),
            ("Grade / Quality", grade),
            (f"Cost per SqFt (Grade {grade})", f"${cost_psf:,.0f}"),
            ("Replacement Cost New", self._fmt(replacement_cost_new)),
        ]
        for label, val in rows:
            self._table_row(pdf, ca_w, [label, val])

        pdf.ln(5)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, "Accrued Depreciation", ln=True)
        dep_w = [80, 50, 60]
        self._table_header(pdf, dep_w, ["Depreciation Type", "Rate / Basis", "Amount"])
        dep_rows = [
            ("Physical Deterioration", f"{effective_age}yr / {economic_life}yr life = {physical_depr_pct*100:.1f}%", f"-{self._fmt(physical_depr_amt)}"),
            ("Functional Obsolescence", "Per condition analysis" if functional_obs > 0 else "None identified", f"-{self._fmt(functional_obs)}" if functional_obs > 0 else "$0"),
            ("External Obsolescence", f"Flood zone ({flood_data.get('zone', 'N/A')})" if external_obs > 0 else "None identified", f"-{self._fmt(external_obs)}" if external_obs > 0 else "$0"),
        ]
        for label, basis, amt in dep_rows:
            self._table_row(pdf, dep_w, [label, basis, amt])

        # Total row
        pdf.set_font("Arial", 'B', 8)
        pdf.set_fill_color(220, 225, 235)
        pdf.cell(dep_w[0], 7, "Total Depreciation", 1, 0, 'L', True)
        pdf.cell(dep_w[1], 7, f"{physical_depr_pct*100:.1f}% + adjustments", 1, 0, 'C', True)
        pdf.cell(dep_w[2], 7, f"-{self._fmt(total_depreciation)}", 1, 1, 'R', True)

        pdf.ln(5)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, "Cost Approach Value Conclusion", ln=True)
        cv_w = [95, 95]
        self._table_header(pdf, cv_w, ["Component", "Value"])
        self._table_row(pdf, cv_w, ["Replacement Cost New", self._fmt(replacement_cost_new)])
        self._table_row(pdf, cv_w, ["Less: Accrued Depreciation", f"-{self._fmt(total_depreciation)}"])
        self._table_row(pdf, cv_w, ["Depreciated Cost of Improvements", self._fmt(depreciated_value)])
        self._table_row(pdf, cv_w, ["Plus: Land Value", self._fmt(land_val)])

        # Final value — highlighted
        pdf.set_font("Arial", 'B', 9)
        pdf.set_fill_color(219, 234, 254)
        pdf.cell(cv_w[0], 8, "  COST APPROACH INDICATED VALUE", 1, 0, 'L', True)
        pdf.cell(cv_w[1], 8, self._fmt(cost_approach_value), 1, 1, 'C', True)

        # Comparison callout
        delta = appraised - cost_approach_value
        if delta > 0:
            pdf.ln(5)
            pdf.set_fill_color(254, 226, 226)
            pdf.rect(15, pdf.get_y(), 180, 18, 'F')
            pdf.set_xy(20, pdf.get_y() + 2)
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(0, 6, "District Over-Assessment vs. Cost Approach", ln=True)
            pdf.set_x(20)
            pdf.set_font("Arial", '', 8)
            pdf.multi_cell(165, 4, clean_text(
                f"The Cost Approach indicates a value of {self._fmt(cost_approach_value)}, which is "
                f"{self._fmt(delta)} ({delta/appraised*100:.1f}%) BELOW the district's appraised value of "
                f"{self._fmt(appraised)}. This independent analysis supports a reduction under "
                f"Texas Tax Code Sec. 23.011 (cost approach as evidence of market value)."
            ))

        # ══════════════════════════════════════════════════════════════════════════
        # ██  ORIGINAL EVIDENCE PAGES (VISION + NARRATIVE)
        # ══════════════════════════════════════════════════════════════════════════

        # ── VISION / PHYSICAL EVIDENCE PAGE ══════════════════════════════════
        if vision_data:
            pdf.add_page()
            self._draw_header(pdf, property_data, "PHYSICAL CONDITION & DEPRECIATION")
            actual_issues = [i for i in vision_data if isinstance(i, dict) and i.get('issue') != 'CONDITION_SUMMARY']
            if actual_issues:
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(0, 10, f"Detected Issues ({len(actual_issues)})", ln=True)
                v_w = [60, 30, 70, 30]
                v_heads = ["Issue", "Severity", "Observation", "Deduction"]
                self._table_header(pdf, v_w, v_heads)
                pdf.set_font("Arial", size=8)
                for issue in actual_issues:
                    pdf.cell(v_w[0], 8, clean_text(issue.get('issue', 'Unknown')), 1)
                    pdf.cell(v_w[1], 8, str(issue.get('severity', 'N/A')), 1, 0, 'C')
                    pdf.cell(v_w[2], 8, clean_text(issue.get('description', ''))[:40], 1)
                    pdf.cell(v_w[3], 8, f"-${issue.get('deduction') or 0:,}", 1, 1, 'R')

            # Total deduction summary
            if condition_deduction > 0:
                pdf.ln(3)
                pdf.set_fill_color(254, 226, 226)
                pdf.set_font("Arial", 'B', 9)
                pdf.cell(130, 8, "  Total Physical Depreciation Deduction:", 0, 0, 'L', True)
                pdf.cell(60, 8, f"-{self._fmt(condition_deduction)}", 0, 1, 'R', True)

            # Add images if available
            if image_paths:
                pdf.ln(5)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(0, 8, "Photographic Evidence", ln=True)
                
                # Grid settings
                margin = 10
                page_width = 190 # 210 - margins
                col_width = (page_width - 5) / 2
                
                start_y = pdf.get_y()
                current_y = start_y
                max_h_row = 0
                
                valid_imgs = [p for p in image_paths if p and os.path.exists(p)][:4]
                
                for i, img_path in enumerate(valid_imgs):
                    col = i % 2
                    
                    # If start of new row (and not first image), advance Y
                    if col == 0 and i > 0:
                        current_y += max_h_row + 5
                        max_h_row = 0
                        # Page break check
                        if current_y > 250:
                            pdf.add_page()
                            current_y = 20
                    
                    x_pos = margin + (col * (col_width + 5))
                    
                    try:
                        # Place image
                        pdf.image(img_path, x=x_pos, y=current_y, w=col_width)
                        # Assume approx height for layout (4:3 aspect is typical, but let's estimate)
                        # We use a fixed height placeholder for layout logic if we can't get actual h
                        # But FPDF usually preserves aspect. 
                        # We'll assume a standard aspect ratio of 0.75 (4:3) for spacing
                        est_h = col_width * 0.75 
                        if max_h_row < est_h: max_h_row = est_h
                    except Exception as e:
                        logger.warning(f"Failed to place image {img_path}: {e}")
                
                # Move cursor past the grid
                pdf.set_y(current_y + max_h_row + 10)

        # ══════════════════════════════════════════════════════════════════════════
        # ██  FORMAL PROTEST NARRATIVE (Texas Tax Code Legal Form)
        # ══════════════════════════════════════════════════════════════════════════
        pdf.add_page()
        self._draw_header(pdf, property_data, "FORMAL PROTEST NARRATIVE")

        # Legal header
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 7, "BEFORE THE APPRAISAL REVIEW BOARD", ln=True, align='C')
        district_name = property_data.get('district', 'Harris County Appraisal District').upper()
        if 'HARRIS' in district_name or 'HCAD' in district_name:
            pdf.cell(0, 7, "HARRIS COUNTY APPRAISAL DISTRICT", ln=True, align='C')
        elif 'TARRANT' in district_name or 'TAD' in district_name:
            pdf.cell(0, 7, "TARRANT APPRAISAL DISTRICT", ln=True, align='C')
        elif 'COLLIN' in district_name or 'CCAD' in district_name:
            pdf.cell(0, 7, "COLLIN CENTRAL APPRAISAL DISTRICT", ln=True, align='C')
        else:
            pdf.cell(0, 7, clean_text(district_name), ln=True, align='C')
        pdf.ln(3)

        # Protest identification
        acct = property_data.get('account_number', 'N/A')
        tax_yr = property_data.get('tax_year', str(current_year))
        owner = property_data.get('owner_name', 'Property Owner')
        address = property_data.get('address', 'N/A')

        pdf.set_font("Arial", '', 9)
        pdf.cell(95, 6, f"Account No: {acct}", ln=False)
        pdf.cell(95, 6, f"Tax Year: {tax_yr}", ln=True)
        pdf.cell(95, 6, f"Owner: {clean_text(owner)}", ln=False)
        pdf.cell(95, 6, f"Subject: {clean_text(address)}", ln=True)
        pdf.ln(3)

        pdf.set_draw_color(30, 41, 59)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        # Grounds for Protest
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 7, "GROUNDS FOR PROTEST", ln=True)
        pdf.set_font("Arial", '', 9)
        pdf.multi_cell(0, 5, clean_text(
            f"Pursuant to Texas Tax Code Sec. 41.41(a), the property owner protests the {tax_yr} "
            f"appraised value of {self._fmt(appraised)} for the property located at {address}, "
            f"Account {acct}, on the following grounds:"
        ))
        pdf.ln(2)

        # Ground 1: Unequal Appraisal
        ground_num = 1
        if equity_floor > 0 and equity_floor < appraised:
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(0, 6, f"Ground {ground_num}: Unequal Appraisal (Sec. 41.43(b)(3) / Sec. 42.26(a)(3))", ln=True)
            pdf.set_font("Arial", '', 8)
            n_comps = len(equity_data.get('equity_5', [])) if isinstance(equity_data, dict) else 0
            pdf.multi_cell(0, 4, clean_text(
                f"The appraised value of {self._fmt(appraised)} exceeds the median appraised value of "
                f"{n_comps} comparable properties appropriately adjusted for differences in size, age, "
                f"condition, and location. The equity analysis yields a justified value floor of "
                f"{self._fmt(equity_floor)}, a difference of {self._fmt(appraised - equity_floor)} "
                f"({(appraised - equity_floor)/appraised*100:.1f}%). Under Sec. 42.26(a)(3), the property "
                f"owner is entitled to relief when the appraised value exceeds the median appraised value "
                f"of comparable properties appropriately adjusted."
            ))
            pdf.ln(2)
            ground_num += 1

        # Ground 2: Market Value Exceeds True Value
        if median_sales > 0 and median_sales < appraised:
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(0, 6, f"Ground {ground_num}: Value Exceeds Market (Sec. 41.43(b)(1) / Sec. 23.01)", ln=True)
            pdf.set_font("Arial", '', 8)
            n_sales = len(sales_data) if sales_data else 0
            pdf.multi_cell(0, 4, clean_text(
                f"The district's appraised value of {self._fmt(appraised)} exceeds the market value "
                f"as established by {n_sales} recent arm's-length sales of comparable properties. "
                f"The median comparable sale price of {self._fmt(median_sales)} represents the most "
                f"probable price the property would bring in a competitive and open market under conditions "
                f"required for a fair sale as defined in Sec. 1.04(7). This constitutes a difference of "
                f"{self._fmt(appraised - median_sales)} ({(appraised - median_sales)/appraised*100:.1f}%)."
            ))
            pdf.ln(2)
            ground_num += 1

        # Ground 3: Physical Condition / Depreciation
        if condition_deduction > 0:
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(0, 6, f"Ground {ground_num}: Physical Depreciation (Sec. 23.01(b) / Sec. 23.012)", ln=True)
            pdf.set_font("Arial", '', 8)
            actual_issues = [i for i in (vision_data or []) if isinstance(i, dict) and i.get('issue') != 'CONDITION_SUMMARY']
            issue_list = ', '.join([i.get('issue', '') for i in actual_issues[:5]])
            pdf.multi_cell(0, 4, clean_text(
                f"Physical inspection identified {len(actual_issues)} condition issues including "
                f"{issue_list}. Total estimated depreciation of {self._fmt(condition_deduction)} "
                f"is not reflected in the current assessment. Per Sec. 23.012, the appraisal must "
                f"consider the condition of the property, including physical deterioration and "
                f"functional or economic obsolescence."
            ))
            pdf.ln(2)
            ground_num += 1

        # Ground 4: Cost Approach (if applicable)
        if cost_approach_value < appraised:
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(0, 6, f"Ground {ground_num}: Cost Approach (Sec. 23.011)", ln=True)
            pdf.set_font("Arial", '', 8)
            pdf.multi_cell(0, 4, clean_text(
                f"Independent cost approach analysis yields an indicated value of "
                f"{self._fmt(cost_approach_value)}, calculated as replacement cost new of "
                f"{self._fmt(replacement_cost_new)} less accrued depreciation of "
                f"{self._fmt(total_depreciation)}, plus land value of {self._fmt(land_val)}. "
                f"This is {self._fmt(appraised - cost_approach_value)} below the district's assessment."
            ))
            pdf.ln(2)
            ground_num += 1

        # Requested Relief
        pdf.ln(3)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 7, "REQUESTED RELIEF", ln=True)
        pdf.set_font("Arial", '', 9)
        pdf.multi_cell(0, 5, clean_text(
            f"Based on the foregoing evidence, the property owner respectfully requests the "
            f"Appraisal Review Board reduce the appraised value from {self._fmt(appraised)} to "
            f"{self._fmt(opinion_val)}, consistent with the lowest indicated value supported by "
            f"the equity, market, cost, and condition evidence presented herein."
        ))

        # Legal basis summary
        pdf.ln(3)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 7, "APPLICABLE TEXAS TAX CODE SECTIONS", ln=True)
        pdf.set_font("Arial", '', 8)
        legal_refs = [
            ("Sec. 1.04(7)", "Definition of market value as most probable price in competitive, open market"),
            ("Sec. 23.01", "Appraisal methods and procedures; consideration of property condition"),
            ("Sec. 23.011", "Cost, income, and market data comparison approaches to value"),
            ("Sec. 23.012", "Factors for physical deterioration and obsolescence"),
            ("Sec. 41.41(a)", "Right to protest before the Appraisal Review Board"),
            ("Sec. 41.43(b)(1)", "Protest ground: value is incorrect / exceeds market value"),
            ("Sec. 41.43(b)(3)", "Protest ground: property is appraised unequally"),
            ("Sec. 42.26(a)(3)", "Relief when value exceeds median of comparable properties, adjusted"),
        ]
        lr_w = [30, 160]
        for code, desc in legal_refs:
            pdf.cell(lr_w[0], 5, code, 0)
            pdf.cell(lr_w[1], 5, clean_text(desc), 0, 1)

        # AI-generated narrative (if provided)
        if narrative and len(narrative) > 50:
            pdf.add_page()
            self._draw_header(pdf, property_data, "SUPPORTING ANALYSIS")
            pdf.set_font("Arial", '', 9)
            pdf.multi_cell(0, 5, clean_text(narrative))

        # ══════════════════════════════════════════════════════════════════════════
        # ██  APPENDIX: EQUITY COMP GRIDS (moved to back per user feedback)
        # ══════════════════════════════════════════════════════════════════════════
        if comps:
            comp_pages = []
            for i in range(0, len(comps), 3):
                comp_pages.append(comps[i:i+3])

            for page_idx, page_comps in enumerate(comp_pages):
                pdf.add_page()
                self._draw_header(pdf, property_data, "APPENDIX: EQUITY COMP GRID")
                
                pdf.set_font("Arial", 'I', 8)
                pdf.set_text_color(100, 100, 100)
                methodology_text = (
                    "Adjustments are calculated using standard appraisal methods: "
                    "Depreciation based on Marshall & Swift residential cost tables. "
                    "Size adjustments applied at 50% of base rate (diminishing returns)."
                )
                pdf.multi_cell(0, 4, clean_text(methodology_text), align='L')
                pdf.set_text_color(0, 0, 0)
                pdf.ln(2)

                n_comps = len(page_comps)
                factor_w = 32
                data_w = int((190 - factor_w) / max(1 + n_comps, 1))
                col_w = [factor_w] + [data_w] * (1 + n_comps)

                start_letter = page_idx * 3
                headers = ["", "Subject"]
                for ci in range(len(page_comps)):
                    headers.append(f"Comp {chr(65 + start_letter + ci)}")

                self._table_header(pdf, col_w, headers, (200, 210, 230))

                def subj_val(key, fmt_fn=None):
                    v = property_data.get(key, '')
                    return fmt_fn(v) if fmt_fn else str(v or 'N/A')

                def comp_val(comp, key, fmt_fn=None):
                    v = comp.get(key, '')
                    return fmt_fn(v) if fmt_fn else str(v or 'N/A')

                def adj_val(comp, key):
                    return self._fmt(comp.get('adjustments', {}).get(key, 0))

                self._table_row(pdf, col_w, ["Prop ID", property_data.get('account_number', '')] + 
                                [comp_val(c, 'account_number') for c in page_comps])
                self._table_row(pdf, col_w, ["Neighborhood", str(nbhd)] + 
                                [str(c.get('neighborhood_code', nbhd)) for c in page_comps])
                self._table_row(pdf, col_w, ["Situs", clean_text(property_data.get('address', ''))[:25]] + 
                                [clean_text(c.get('address', ''))[:25] for c in page_comps])

                self._table_row(pdf, col_w, ["Year Built", str(property_data.get('year_built', ''))] + 
                                [str(c.get('year_built', '')) for c in page_comps])
                self._table_row(pdf, col_w, ["Market Value", self._fmt(appraised)] + 
                                [self._fmt(c.get('appraised_value', 0)) for c in page_comps])
                self._table_row(pdf, col_w, ["Total SQFT", f"{subj_area:,.0f} SF"] + 
                                [f"{c.get('building_area', 0):,.0f} SF" for c in page_comps])
                self._table_row(pdf, col_w, ["Market Price/SQFT", self._pps(appraised, subj_area)] + 
                                [self._pps(c.get('appraised_value', 0), c.get('building_area', 1)) for c in page_comps])

                pdf.ln(2)

                subj_grade_disp = str(property_data.get('building_grade', 'N/A'))
                subj_year_built = str(property_data.get('year_built', ''))

                self._table_row(pdf, col_w, ["TTL Cost Factor", ""] + ["" for _ in page_comps])
                self._table_row(pdf, col_w, ["Year Remodeled", subj_year_built] + 
                                [str(c.get('adjustments', {}).get('comp_remodel', c.get('year_built', ''))) for c in page_comps])
                
                remodel_label = "New/Rebuilt" if property_data.get('year_built') and int(str(property_data.get('year_built'))[:4]) >= (datetime.datetime.now().year - 5) else str(property_data.get('year_built', ''))
                self._table_row(pdf, col_w, ["Remodel Adj", remodel_label] + 
                                [self._fmt(c.get('adjustments', {}).get('remodel', 0)) for c in page_comps])

                self._table_row(pdf, col_w, ["Grade Adj", subj_grade_disp] + 
                                [f"{c.get('adjustments', {}).get('comp_grade', 'N/A')} {adj_val(c, 'grade')}" for c in page_comps])
                self._table_row(pdf, col_w, ["Size Index Adj", ""] + 
                                [adj_val(c, 'size') for c in page_comps])
                self._table_row(pdf, col_w, ["Neighborhood Adj", str(nbhd)] + 
                                [f"{c.get('neighborhood_code', nbhd)} {adj_val(c, 'neighborhood')}" for c in page_comps])
                self._table_row(pdf, col_w, ["% Good Adj", f"{page_comps[0].get('adjustments', {}).get('subject_pct_good', 97)}%"] + 
                                [f"{c.get('adjustments', {}).get('comp_pct_good', 80)}% {adj_val(c, 'percent_good')}" for c in page_comps])

                pdf.ln(2)
                self._table_row(pdf, col_w, ["Size Adj", "-"] + [adj_val(c, 'size') for c in page_comps])
                pdf.ln(2)
                self._table_row(pdf, col_w, ["Lump Sum Adj", ""] + [adj_val(c, 'lump_sum') for c in page_comps])
                pdf.ln(2)
                self._table_row(pdf, col_w, ["Sub Area Diff", ""] + [adj_val(c, 'sub_area_diff') for c in page_comps])
                pdf.ln(2)

                self._table_row(pdf, col_w, ["Land Value Adj", self._fmt(subj_land)] + [adj_val(c, 'land_value') for c in page_comps])
                self._table_row(pdf, col_w, ["Segments & Adj", "$0"] + [adj_val(c, 'segments') for c in page_comps])
                self._table_row(pdf, col_w, ["Other Improvements", "$0"] + [adj_val(c, 'other_improvements') for c in page_comps])

                pdf.ln(2)

                pdf.set_fill_color(230, 240, 255)
                pdf.set_font("Arial", 'B', 7)
                net_vals = ["Net Adjustment", ""]
                for c in page_comps:
                    net_vals.append(self._fmt(c.get('adjustments', {}).get('net_adjustment', 0)))
                for i, v in enumerate(net_vals):
                    pdf.cell(col_w[i], 8, clean_text(str(v)), 1, 0, 'C' if i > 0 else 'L', True)
                pdf.ln()

                pdf.ln(1)

                ind_vals = ["Indicated Value", ""]
                for c in page_comps:
                    ind_vals.append(self._fmt(c.get('adjustments', {}).get('indicated_value', 0)))
                pdf.set_fill_color(220, 255, 220)
                for i, v in enumerate(ind_vals):
                    pdf.cell(col_w[i], 8, clean_text(str(v)), 1, 0, 'C' if i > 0 else 'L', True)
                pdf.ln()

                pdf.ln(3)
                median_equity = equity_floor
                pdf.set_font("Arial", 'B', 8)
                pdf.cell(90, 8, f"Median Equity Value: {self._fmt(median_equity)}", 0, 0, 'L')
                pdf.cell(90, 8, f"Median Equity Value / SQFT: {self._pps(median_equity, subj_area)}", 0, 1, 'R')

        # ── EQUITY MAP PAGE (appendix) ════════════════════════════════════════
        if comps:
            pdf.add_page()
            self._draw_header(pdf, property_data, "APPENDIX: EQUITY GEOGRAPHIC CONTEXT")
            addrs = [c.get('address') for c in comps[:7] if c.get('address')]
            map_p = self._generate_static_map(property_data.get('address'), addrs, "blue")
            if map_p:
                pdf.image(map_p, x=10, y=40, w=190)
                try: os.unlink(map_p)
                except: pass
            else:
                pdf.set_font("Arial", '', 10)
                pdf.ln(20)
                pdf.cell(0, 10, "Map: Google Maps API key required for geographic context.", ln=True, align='C')
            pdf.set_y(200)
            pdf.set_font("Arial", 'B', 8)
            pdf.cell(0, 6, f"Owner Name: {clean_text(owner_name)}  |  Address: {clean_text(property_data.get('address', ''))}", ln=True)
            pdf.cell(0, 6, f"Account Number: {property_data.get('account_number', '')}  |  {clean_text(property_data.get('address', ''))}", ln=True)

        # Signature block
        pdf.ln(8)
        pdf.set_font("Arial", '', 9)
        pdf.cell(0, 6, f"Respectfully submitted,", ln=True)
        pdf.ln(10)
        pdf.cell(0, 6, "_" * 40, ln=True)
        pdf.cell(0, 6, f"{clean_text(owner)}, Property Owner", ln=True)
        pdf.cell(0, 6, f"Date: {datetime.datetime.now().strftime('%B %d, %Y')}", ln=True)

        # ── Output ────────────────────────────────────────────────────────────
        pdf.output(output_path)
        return output_path
