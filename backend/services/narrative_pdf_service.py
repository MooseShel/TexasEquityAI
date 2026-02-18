import os
from google import genai
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from fpdf import FPDF
import logging
import re

def clean_text(text: str) -> str:
    """Replace non-latin-1 characters like smart quotes with ASCII equivalents."""
    if not text:
        return ""
    # Very aggressive replacement for common Unicode hurdles
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
        "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
        "\u2013": "-", "\u2014": "-", "\u2015": "-",
        "\u2026": "...", "\u2022": "*", "\u00b7": "*",
        "\u00a7": "Sect.", "\u00a9": "(C)", "\u00ae": "(R)", "\u2122": "(TM)"
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    
    # Final safety: encode to ASCII and ignore errors to be 100% sure for basic FPDF
    return text.encode('ascii', 'ignore').decode('ascii')

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
        
        Evidence 1: Market Value (Sales Comparison)
        - Recent Market Price/Estimate: ${market_value}
        
        Evidence 2: Equity Evidence (Equity 5)
        - Median Justified Value: ${justified_value}
        - Key Comparables on the same street: {comparables}
        
        Evidence 3: Condition & Location Issues
        - Identified Issues: {issues}
        - Total Condition Deduction: ${total_deduction}
        
        Evidence 4: Comparative Permit History
        - Subject Renovation Status: {subject_permits}
        - Comparable Renovations: {comp_renovations}
        
        Evidence 5: Flood Risk Analysis
        - FEMA Flood Zone: {flood_zone}
        
        EQUITY SITUATION: {equity_situation}
        
        The narrative MUST cite:
        - Texas Tax Code §41.43 (Uniform and Equal)
        - Texas Tax Code §41.41 (Market Value)
        
        Structure it professionally for an Appraisal Review Board (ARB) hearing.
        {equity_argument}
        Use the Flood Risk and Permit lack-of-renovation to argue for additional 'External Obsolescence' and 'Physical Depreciation' adjustments where applicable.
        IMPORTANT: Only argue positions that are supported by the data above. Do NOT claim the appraised value exceeds comparable values if the justified value is higher than the appraised value.
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
                "justified value floor under Texas Tax Code §41.43 (Uniform and Equal)."
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
        
        inputs = {
            "address": property_data.get('address', 'N/A'),
            "account_number": property_data.get('account_number', 'N/A'),
            "appraised_value": f"{appraised_val:,.0f}",
            "building_area": property_data.get('building_area', 0),
            "market_value": f"{market_val:,.0f}" if market_val else "N/A",
            "justified_value": f"{justified_val:,.0f}",
            "comparables": ", ".join([c.get('address', 'N/A') for c in equity_data.get('equity_5', [])]) if isinstance(equity_data, dict) and 'equity_5' in equity_data else "None cited",
            "issues": ", ".join([d.get('issue', 'Unknown') for d in visible_issues]) if visible_issues else "None cited",
            "total_deduction": sum(d.get('deduction', 0) for d in visible_issues) if visible_issues else 0,
            "subject_permits": property_data.get('permit_summary', {}).get('status', 'No major permits found'),
            "comp_renovations": "; ".join([f"{c['address']} has {len(c['renovations'])} major permits" for c in property_data.get('comp_renovations', [])]) or "No major renovations found in comps",
            "flood_zone": property_data.get('flood_zone', 'Zone X (Minimal Risk)'),
            "equity_situation": equity_situation,
            "equity_argument": equity_argument,
        }

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
        
        # Fallback to Gemini
        if self.gemini_client:
            try:
                logger.info("Attempting narrative generation with Gemini (Fallback)...")
                # Direct SDK Usage - bypass LangChain
                # Reconstruct prompt manually since we aren't using the chain
                final_prompt = prompt.format(**inputs)
                
                response = self.gemini_client.models.generate_content(
                    model='gemini-2.0-flash', 
                    contents=final_prompt
                )
                return clean_text(response.text)
            except Exception as e:
                logger.error(f"Gemini Fallback failed: {e}")
                return f"Error: All LLM providers (OpenAI, xAI, Gemini) failed to generate narrative. Last error: {e}"

        return "Error: No viable LLM available for generation."

class PDFService:
    def generate_evidence_packet(self, narrative: str, property_data: dict, equity_data: dict, vision_data: list, output_path: str):
        pdf = FPDF()
        pdf.add_page()
        
        # Title
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="Texas Equity AI - Evidence Packet", ln=True, align='C')
        pdf.ln(10)
        
        # Property Info
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 10, txt=f"Property: {property_data.get('address')}", ln=True)
        pdf.cell(200, 10, txt=f"Account: {property_data.get('account_number')}", ln=True)
        pdf.ln(5)
        
        # Narrative
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Protest Narrative", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 10, txt=clean_text(narrative))
        pdf.ln(10)
        
        # Equity 5 Table
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Equity 5 Comparables", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.cell(80, 10, "Address", 1)
        pdf.cell(40, 10, "Value/SqFt", 1)
        pdf.cell(40, 10, "Building Area", 1)
        pdf.ln()
        
        for comp in equity_data.get('equity_5', []):
            pdf.cell(80, 10, str(comp.get('address', 'N/A')), 1)
            pdf.cell(40, 10, f"${comp.get('value_per_sqft', 0):.2f}", 1)
            pdf.cell(40, 10, str(comp.get('building_area', 0)), 1)
            pdf.ln()
        
        pdf.output(output_path)
        return output_path
