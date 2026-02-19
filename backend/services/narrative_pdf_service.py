import os
from google import genai
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from fpdf import FPDF
import logging
import re

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
        # Unicode spaces — must be replaced with a regular space BEFORE ascii encode
        # otherwise words get squashed together
        "\u00a0": " ",   # non-breaking space
        "\u2009": " ",   # thin space
        "\u200a": " ",   # hair space
        "\u2002": " ",   # en space
        "\u2003": " ",   # em space
        "\u202f": " ",   # narrow no-break space
        "\u205f": " ",   # medium mathematical space
        "\u3000": " ",   # ideographic space
        "\u200b": "",    # zero-width space (just drop it)
        "\u200c": "",    # zero-width non-joiner
        "\u200d": "",    # zero-width joiner
        "\ufeff": "",    # BOM
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    # Final safety: encode to latin-1 range (not strict ASCII) to handle accented chars
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
                # Initialize direct Google GenAI Client
                self.gemini_client = genai.Client(api_key=self.gemini_key)
                logger.info("Gemini Client initialized (google-genai).")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")

        if self.openai_key:
            try:
                self.openai_llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    api_key=self.openai_key,
                    temperature=0.7
                )
                logger.info("OpenAI LLM initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")

        if self.xai_key:
            try:
                # Grok AI is OpenAI-compatible
                self.xai_llm = ChatOpenAI(
                    model="grok-2-latest",
                    api_key=self.xai_key,
                    base_url="https://api.x.ai/v1",
                    temperature=0.7
                )
                logger.info("xAI (Grok) LLM initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize xAI: {e}")

    def generate_protest_narrative(self, property_data: dict, equity_data: dict, vision_data: list, market_value: float = None) -> str:
        """
        Synthesize Scraper, Equity, Market, and Vision data into a formal protest narrative.
        LCEL Syntax: prompt | llm | output_parser
        """
        if not self.gemini_client and not self.openai_llm and not self.xai_llm:
            return "Narrative Generation Unavailable: No LLM keys (Gemini/OpenAI/xAI) found or initialization failed."

        prompt_template = """
        You are an expert Property Tax Consultant in Texas. 
        Write a formal protest narrative for the following property:
        
        Property Details:
        - Address: {address}
        - Account Number: {account_number}
        - Current Appraised Value: ${appraised_value}
        - Building Area: {building_area} sqft
        
        Evidence 1: Unequal Appraisal (Equity Analysis per §41.43(b)(1))
        - Median Justified Value from Equity Comparables: ${justified_value}
        - Key Equity Comparables (same neighborhood): {comparables}
        
        Evidence 2: Market Value (Sales Comparison per §41.43(b)(3))
        - Recent Market Price/Estimate: ${market_value}
        - Number of Recent Sales Comps: {sales_comp_count}
        - Median Recent Sale Price: ${median_sale_price}
        - Average Sale Price per SqFt: ${avg_sale_pps}
        - Sales Comps Detail: {sales_comps_detail}
        
        Evidence 3: Condition & Location Issues (Physical Depreciation - Texas §23.013)
        - Condition Score: {condition_score}/10 (10=excellent, 1=condemned)
        - Effective Age Estimate: {effective_age} years
        - Identified Issues (name, severity, estimated deduction):
          {issues_detail}
        - Category Totals:
          Physical Deterioration: ${total_physical}
          Functional Obsolescence: ${total_functional}
          External Obsolescence: ${total_external}
          TOTAL DEDUCTION: ${total_deduction}
        
        Evidence 4: Comparative Permit History
        - Subject Renovation Status: {subject_permits}
        - Comparable Renovations: {comp_renovations}
        
        Evidence 5: Flood Risk Analysis (External Obsolescence)
        - FEMA Flood Zone: {flood_zone}
        
        EQUITY SITUATION: {equity_situation}
        SALES SITUATION: {sales_situation}
        
        The narrative MUST cite applicable Texas Tax Code sections:
        - Texas Tax Code Sect.41.43(b)(1) - Unequal Appraisal
        - Texas Tax Code Sect.41.43(b)(3) - Market Value
        - Texas Tax Code Sect.23.01 - Appraisal Methods
        
        Structure it professionally for an Appraisal Review Board (ARB) hearing.
        {equity_argument}
        {sales_argument}
        
        For Evidence 3 (Condition): 
        - If issues_detail is NOT "None identified", name each issue explicitly with its deduction amount.
        - If issues_detail IS "None identified", write ONE sentence acknowledging no exterior defects were visible from street-level imagery. Do NOT pad this section with generic text.
        
        CRITICAL FORMATTING RULES:
        - Write all dollar values as plain text (e.g. "$1,961,533" not "$1,961,533surpasses...").
        - DO NOT use LaTeX, markdown math, or any special formatting for numbers.
        - Use normal prose with standard punctuation. Do not join words together.
        - Write plain paragraphs. No special characters or Unicode math symbols.
        IMPORTANT: Only argue positions supported by data. Do NOT claim over-assessment if the justified value is higher than the appraised value.
        """
        
        prompt = PromptTemplate.from_template(prompt_template)
        # Safety Guard: Ensure vision_data is a list
        visible_issues = []
        if isinstance(vision_data, list):
            visible_issues = [d for d in vision_data if isinstance(d, dict)]
        
        # ── Equity Direction Analysis ─────────────────────────────────────────
        appraised_val = property_data.get('appraised_value', 0) or 0
        justified_val = equity_data.get('justified_value_floor', 0) if isinstance(equity_data, dict) else 0
        justified_val = justified_val or 0
        market_val = market_value or appraised_val
        
        # Determine if the property is over or under assessed
        is_over_assessed_equity = justified_val > 0 and appraised_val > justified_val
        is_over_assessed_market = market_val > 0 and appraised_val > market_val
        potential_savings = max(0, appraised_val - justified_val) if justified_val > 0 else 0
        
        if is_over_assessed_equity:
            equity_situation = (
                f"OVER-ASSESSED: The appraised value (${appraised_val:,.0f}) EXCEEDS the "
                f"median justified value of comparable properties (${justified_val:,.0f}), "
                f"suggesting a potential over-assessment of ${potential_savings:,.0f}."
            )
            equity_argument = (
                "Focus on how the Appraised Value exceeds both the actual market value and the "
                "median equity value of similar homes (Equity 5). Argue for a reduction to the "
                "justified value floor under Texas Tax Code §41.43(b)(1) (Unequal Appraisal)."
            )
        elif justified_val > appraised_val:
            equity_situation = (
                f"UNDER-ASSESSED relative to comps: The median justified value of comparable "
                f"properties (${justified_val:,.0f}) is HIGHER than the appraised value "
                f"(${appraised_val:,.0f}). The equity argument does NOT support a reduction. "
                f"Focus protest on market value and condition/location issues instead."
            )
            equity_argument = (
                "The comparable property analysis does NOT show over-assessment — do NOT claim "
                "the appraised value exceeds comparable values. Instead, focus the protest on: "
                "(1) any gap between appraised value and actual market value, "
                "(2) physical condition issues identified in the property inspection, "
                "(3) external obsolescence factors (flood risk, deferred maintenance). "
                "If the appraised value is already below market, acknowledge this but argue "
                "that condition and location factors justify a lower value."
            )
        else:
            equity_situation = "Equity data unavailable or insufficient comparables found."
            equity_argument = (
                "Focus the protest on market value evidence and any condition/location issues. "
                "Do not make equity uniformity arguments without supporting comparable data."
            )
        
        # ── Sales Comparable Analysis ─────────────────────────────────────────
        sales_comps = equity_data.get('sales_comps', []) if isinstance(equity_data, dict) else []
        sales_comp_count = len(sales_comps)
        median_sale_price = 0
        avg_sale_pps = 0
        sales_comps_detail = "No recent sales data available."
        sales_situation = "No sales comparable data available."
        sales_argument = ""
        
        if sales_comps:
            # Parse prices from formatted strings
            prices = []
            pps_vals = []
            for sc in sales_comps:
                try:
                    p = float(str(sc.get('Sale Price', '0')).replace('$', '').replace(',', ''))
                    if p > 0: prices.append(p)
                except: pass
                try:
                    pp = float(str(sc.get('Price/SqFt', '0')).replace('$', '').replace(',', ''))
                    if pp > 0: pps_vals.append(pp)
                except: pass
            
            if prices:
                prices.sort()
                mid = len(prices) // 2
                median_sale_price = prices[mid] if len(prices) % 2 else (prices[mid-1] + prices[mid]) / 2
            if pps_vals:
                avg_sale_pps = sum(pps_vals) / len(pps_vals)
            
            # Build detail string (top 5 closest comps)
            detail_lines = []
            for sc in sales_comps[:5]:
                detail_lines.append(
                    f"{sc.get('Address', 'N/A')} — {sc.get('Sale Price', 'N/A')} "
                    f"({sc.get('SqFt', 'N/A')} sqft, {sc.get('Price/SqFt', 'N/A')}/sqft, "
                    f"{sc.get('Distance', 'N/A')} away, sold {sc.get('Sale Date', 'N/A')})"
                )
            sales_comps_detail = "; ".join(detail_lines)
            
            if median_sale_price > 0 and appraised_val > median_sale_price:
                sales_gap = appraised_val - median_sale_price
                sales_situation = (
                    f"OVER-APPRAISED vs MARKET: The appraised value (${appraised_val:,.0f}) EXCEEDS "
                    f"the median recent sale price of {sales_comp_count} comparable sales "
                    f"(${median_sale_price:,.0f}) by ${sales_gap:,.0f}. "
                    f"Average sale price per sqft is ${avg_sale_pps:.2f}."
                )
                sales_argument = (
                    f"Cite the {sales_comp_count} recent comparable sales to argue the appraised "
                    f"value exceeds market value under Texas Tax Code §41.43(b)(3) and §23.01. "
                    f"The median sale price of ${median_sale_price:,.0f} and average $/sqft of "
                    f"${avg_sale_pps:.2f} both support a reduction."
                )
            elif median_sale_price > 0:
                sales_situation = (
                    f"Appraised value (${appraised_val:,.0f}) is at or below the median sale price "
                    f"(${median_sale_price:,.0f}) of {sales_comp_count} recent sales. "
                    f"Sales data does not independently support a reduction, but can corroborate "
                    f"other arguments. Avg $/sqft: ${avg_sale_pps:.2f}."
                )
                sales_argument = (
                    "Present sales data as corroborating evidence for market value context, "
                    "but do NOT claim the appraised value exceeds market-indicated value from sales."
                )
        
        inputs = {
            "address": property_data.get('address', 'N/A'),
            "account_number": property_data.get('account_number', 'N/A'),
            "appraised_value": f"{appraised_val:,.0f}",
            "building_area": property_data.get('building_area', 0),
            "market_value": f"{market_val:,.0f}" if market_val else "N/A",
            "justified_value": f"{justified_val:,.0f}",
            "comparables": ", ".join([c.get('address', 'N/A') for c in equity_data.get('equity_5', [])]) if isinstance(equity_data, dict) and 'equity_5' in equity_data else "None cited",
            "sales_comp_count": sales_comp_count,
            "median_sale_price": f"{median_sale_price:,.0f}" if median_sale_price else "N/A",
            "avg_sale_pps": f"{avg_sale_pps:.2f}" if avg_sale_pps else "N/A",
            "sales_comps_detail": sales_comps_detail,
        }

        # ── Extract Vision Summary & Build Detailed Issues ─────────────────
        condition_score = "N/A"
        effective_age = "N/A"
        total_physical = 0
        total_functional = 0
        total_external = 0
        issues_detail_lines = []
        actual_issues = []
        for item in visible_issues:
            if item.get('issue') == 'CONDITION_SUMMARY':
                condition_score = item.get('condition_score', 'N/A')
                effective_age = item.get('effective_age', 'N/A')
                total_physical = item.get('total_physical', 0)
                total_functional = item.get('total_functional', 0)
                total_external = item.get('total_external', 0)
            else:
                actual_issues.append(item)
                ded = item.get('deduction', 0)
                sev = item.get('severity', 'Unknown')
                cat = item.get('category', 'Physical Deterioration')
                issues_detail_lines.append(
                    f"  - {item.get('issue', 'Unknown')} [{sev}] ({cat}): ${ded:,.0f} deduction"
                )
        
        issues_detail = "\n".join(issues_detail_lines) if issues_detail_lines else "None identified"
        total_deduction = sum(d.get('deduction', 0) for d in actual_issues) if actual_issues else 0

        inputs.update({
            "condition_score": condition_score,
            "effective_age": effective_age,
            "issues_detail": issues_detail,
            "total_physical": f"{total_physical:,.0f}" if isinstance(total_physical, (int, float)) else str(total_physical),
            "total_functional": f"{total_functional:,.0f}" if isinstance(total_functional, (int, float)) else str(total_functional),
            "total_external": f"{total_external:,.0f}" if isinstance(total_external, (int, float)) else str(total_external),
            "total_deduction": f"{total_deduction:,.0f}" if isinstance(total_deduction, (int, float)) else str(total_deduction),
            "subject_permits": property_data.get('permit_summary', {}).get('status', 'No major permits found'),
            "comp_renovations": "; ".join([f"{c['address']} has {len(c['renovations'])} major permits" for c in property_data.get('comp_renovations', [])]) or "No major renovations found in comps",
            "flood_zone": property_data.get('flood_zone', 'Zone X (Minimal Risk)'),
            "equity_situation": equity_situation,
            "equity_argument": equity_argument,
            "sales_situation": sales_situation,
            "sales_argument": sales_argument,
        })

        # Try OpenAI First
        if self.openai_llm:
            try:
                logger.info("Attempting narrative generation with OpenAI (Primary)...")
                chain = prompt | self.openai_llm | StrOutputParser()
                narrative = chain.invoke(inputs)
                return clean_text(narrative)
            except Exception as e:
                logger.warning(f"OpenAI failed: {e}. Falling back to Grok AI...")
        
        # Fallback to xAI (Grok)
        if self.xai_llm:
            try:
                logger.info("Attempting narrative generation with xAI Grok (Fallback)...")
                chain = prompt | self.xai_llm | StrOutputParser()
                narrative = chain.invoke(inputs)
                return clean_text(narrative)
            except Exception as e:
                logger.warning(f"xAI Fallback failed: {e}. Falling back to Gemini...")
        
        # Fallback to Gemini (with retry for 429s)
        if self.gemini_client:
            import time
            retries = [15, 30]
            for attempt in range(len(retries) + 1):
                try:
                    logger.info(f"Attempting narrative generation with Gemini (attempt {attempt + 1})...")
                    final_prompt = prompt.format(**inputs)
                    
                    response = self.gemini_client.models.generate_content(
                        model='gemini-2.0-flash', 
                        contents=final_prompt
                    )
                    return clean_text(response.text)
                except Exception as e:
                    error_str = str(e)
                    if '429' in error_str and attempt < len(retries):
                        delay = retries[attempt]
                        logger.warning(f"Gemini 429 rate limit — retrying in {delay}s (attempt {attempt + 1})...")
                        time.sleep(delay)
                    else:
                        logger.error(f"Gemini Fallback failed: {e}")
                        return f"Error: All LLM providers (OpenAI, xAI, Gemini) failed to generate narrative. Last error: {e}"

        return "Error: No viable LLM available for generation."

class PDFService:
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_STREET_VIEW_API_KEY")

    def _generate_static_map(self, subject_addr: str, comp_addresses: list, label_color: str = "blue") -> str:
        """Generate a Google Static Map image with markers, return temp file path or None."""
        if not self.google_api_key:
            return None
        try:
            import requests as req
            import tempfile

            markers = [f"color:red|label:S|{subject_addr}"]
            for i, addr in enumerate(comp_addresses[:5]):
                label = chr(65 + i)
                markers.append(f"color:{label_color}|label:{label}|{addr}")

            url = "https://maps.googleapis.com/maps/api/staticmap"
            marker_str = "&".join([f"markers={m}" for m in markers])
            full_url = f"{url}?size=640x400&maptype=roadmap&key={self.google_api_key}&{marker_str}"

            resp = req.get(full_url, timeout=10)
            if resp.status_code == 200 and resp.headers.get('content-type', '').startswith('image'):
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                tmp.write(resp.content)
                tmp.close()
                return tmp.name
            else:
                logger.warning(f"Static Maps API returned status {resp.status_code}")
        except Exception as e:
            logger.warning(f"Static map generation failed: {e}")
        return None

    def generate_evidence_packet(self, narrative: str, property_data: dict, equity_data: dict,
                                  vision_data: list, output_path: str, sales_data: list = None,
                                  image_paths: list = None):
        pdf = FPDF()
        pdf.add_page()
        
        # Title
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="Texas Equity AI - Evidence Packet", ln=True, align='C')
        pdf.ln(10)
        
        # Property Info
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 10, txt=clean_text(f"Property: {property_data.get('address')}"), ln=True)
        pdf.cell(200, 10, txt=clean_text(f"Account: {property_data.get('account_number')}"), ln=True)
        pdf.ln(5)
        
        # Narrative
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Protest Narrative", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 6, txt=clean_text(narrative))
        pdf.ln(10)
        
        # ── Equity 5 Table ──────────────────────────────────
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Equity 5 Comparables", ln=True)
        pdf.set_font("Arial", size=9)
        
        col_w = [65, 28, 28, 32]
        headers = ["Address", "Value/SqFt", "Bldg Area", "Appraised"]
        for i, h in enumerate(headers):
            pdf.cell(col_w[i], 8, h, 1)
        pdf.ln()
        
        equity_addrs = []
        for comp in equity_data.get('equity_5', []):
            addr = str(comp.get('address', 'N/A'))
            equity_addrs.append(addr)
            pdf.cell(col_w[0], 8, clean_text(addr[:32]), 1)
            pdf.cell(col_w[1], 8, f"${comp.get('value_per_sqft', 0):.2f}", 1)
            pdf.cell(col_w[2], 8, f"{comp.get('building_area', 0):,}", 1)
            pdf.cell(col_w[3], 8, f"${comp.get('appraised_value', 0):,.0f}", 1)
            pdf.ln()
        
        # Equity Map
        subject_addr = property_data.get('address', '')
        map_path = self._generate_static_map(subject_addr, equity_addrs, label_color="blue")
        if map_path:
            pdf.ln(3)
            pdf.image(map_path, x=10, w=190)
            pdf.ln(3)
            try:
                os.unlink(map_path)
            except:
                pass

        # ── Sales Comps Table ───────────────────────────────
        if sales_data and len(sales_data) > 0:
            pdf.add_page()
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(200, 10, txt="Sales Comparable Analysis", ln=True)
            pdf.set_font("Arial", size=9)

            s_col_w = [55, 27, 27, 22, 22, 22]
            s_headers = ["Address", "Sale Price", "Sale Date", "Sq Ft", "$/SqFt", "Distance"]
            for i, h in enumerate(s_headers):
                pdf.cell(s_col_w[i], 8, h, 1)
            pdf.ln()

            sales_addrs = []
            for sc in sales_data[:5]:
                addr = str(sc.get('Address', 'N/A'))
                sales_addrs.append(addr)
                raw_date = str(sc.get('Sale Date', ''))
                if raw_date and raw_date != 'None':
                    try:
                        from datetime import datetime as dt
                        date_str = raw_date.split('T')[0]
                        parsed = dt.strptime(date_str, '%Y-%m-%d')
                        fmt_date = parsed.strftime('%m/%d/%Y')
                    except:
                        fmt_date = raw_date[:10]
                else:
                    fmt_date = "N/A"

                pdf.cell(s_col_w[0], 8, clean_text(addr[:27]), 1)
                pdf.cell(s_col_w[1], 8, clean_text(str(sc.get('Sale Price', 'N/A'))), 1)
                pdf.cell(s_col_w[2], 8, fmt_date, 1)
                pdf.cell(s_col_w[3], 8, clean_text(str(sc.get('SqFt', 'N/A'))), 1)
                pdf.cell(s_col_w[4], 8, clean_text(str(sc.get('Price/SqFt', 'N/A'))), 1)
                pdf.cell(s_col_w[5], 8, clean_text(str(sc.get('Distance', 'N/A'))), 1)
                pdf.ln()

            # Sales Map
            map_path = self._generate_static_map(subject_addr, sales_addrs, label_color="green")
            if map_path:
                pdf.ln(3)
                pdf.image(map_path, x=10, w=190)
                pdf.ln(3)
                try:
                    os.unlink(map_path)
                except:
                    pass
        
        # ── Vision / Condition Analysis ─────────────────────
        if vision_data and len(vision_data) > 0:
            pdf.add_page()
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(200, 10, txt="Property Condition Analysis", ln=True)
            
            # Separate summary from issues
            condition_summary = None
            actual_issues = []
            for item in vision_data:
                if isinstance(item, dict):
                    if item.get('issue') == 'CONDITION_SUMMARY':
                        condition_summary = item
                    else:
                        actual_issues.append(item)
            
            # Condition overview
            if condition_summary:
                pdf.set_font("Arial", size=10)
                score = condition_summary.get('condition_score', 'N/A')
                eff_age = condition_summary.get('effective_age', 'N/A')
                pdf.cell(95, 8, f"Condition Score: {score}/10", 0)
                pdf.cell(95, 8, f"Effective Age: {eff_age} years", 0)
                pdf.ln()
                pdf.ln(3)
            
            # Defects table
            if actual_issues:
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(200, 8, txt=f"{len(actual_issues)} Condition Issue(s) Identified", ln=True)
                pdf.set_font("Arial", size=8)
                
                v_col_w = [50, 20, 45, 28, 22]
                v_headers = ["Issue", "Severity", "Category", "Deduction", "Confidence"]
                for i, h in enumerate(v_headers):
                    pdf.cell(v_col_w[i], 7, h, 1)
                pdf.ln()
                
                for issue in actual_issues:
                    pdf.cell(v_col_w[0], 7, clean_text(str(issue.get('issue', 'N/A'))[:25]), 1)
                    pdf.cell(v_col_w[1], 7, str(issue.get('severity', 'N/A')), 1)
                    pdf.cell(v_col_w[2], 7, clean_text(str(issue.get('category', 'N/A'))[:22]), 1)
                    ded = issue.get('deduction', 0)
                    pdf.cell(v_col_w[3], 7, f"${ded:,.0f}" if isinstance(ded, (int, float)) else str(ded), 1)
                    conf = issue.get('confidence', 0)
                    pdf.cell(v_col_w[4], 7, f"{conf*100:.0f}%" if isinstance(conf, (int, float)) else str(conf), 1)
                    pdf.ln()
                
                # Depreciation breakdown
                pdf.ln(5)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(200, 8, txt="Depreciation Breakdown", ln=True)
                pdf.set_font("Arial", size=9)
                
                phys = sum(i.get('deduction', 0) for i in actual_issues if i.get('category', '') == 'Physical Deterioration')
                func = sum(i.get('deduction', 0) for i in actual_issues if i.get('category', '') == 'Functional Obsolescence')
                ext = sum(i.get('deduction', 0) for i in actual_issues if i.get('category', '') == 'External Obsolescence')
                total = phys + func + ext
                
                dep_w = [80, 40]
                for label, val in [("Physical Deterioration", phys), ("Functional Obsolescence", func), 
                                    ("External Obsolescence", ext)]:
                    pdf.cell(dep_w[0], 7, label, 1)
                    pdf.cell(dep_w[1], 7, f"${val:,.0f}", 1)
                    pdf.ln()
                pdf.set_font("Arial", 'B', 9)
                pdf.cell(dep_w[0], 7, "TOTAL DEPRECIATION", 1)
                pdf.cell(dep_w[1], 7, f"${total:,.0f}", 1)
                pdf.ln()
            else:
                pdf.set_font("Arial", size=10)
                pdf.cell(200, 8, txt="No condition issues detected from exterior imagery.", ln=True)
            
            # Annotated Street View images
            image_paths = image_paths or []
            valid_imgs = [p for p in image_paths if p and os.path.exists(p)]
            if valid_imgs:
                pdf.ln(5)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(200, 8, txt="Street View Evidence Images", ln=True)
                labels = ["Front View", "Left 45 View", "Right 45 View"]
                for idx, img in enumerate(valid_imgs[:3]):
                    try:
                        lbl = labels[idx] if idx < len(labels) else f"Angle {idx+1}"
                        pdf.set_font("Arial", size=8)
                        pdf.cell(200, 6, txt=lbl, ln=True)
                        pdf.image(img, x=10, w=140)
                        pdf.ln(3)
                    except Exception as img_err:
                        logger.warning(f"Could not embed image {img}: {img_err}")
        
        pdf.output(output_path)
        return output_path

