import os
from langchain_google_genai import ChatGoogleGenerativeAI
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
        self.gemini_llm = None
        self.openai_llm = None
        self.xai_llm = None

        if self.gemini_key:
            try:
                # Configure for Gemini 2.0 Flash (Verified available in this environment)
                self.gemini_llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash", 
                    google_api_key=self.gemini_key,
                    temperature=0.7
                )
                logger.info("Gemini LLM initialized.")
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
        if not self.gemini_llm and not self.openai_llm and not self.xai_llm:
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
        
        The narrative MUST cite:
        - Texas Tax Code §41.43 (Uniform and Equal)
        - Texas Tax Code §41.41 (Market Value)
        
        Structure it professionally for an HCAD Appraisal Review Board (ARB) hearing.
        Focus on how the Appraised Value exceeds both the actual market value and the median equity value of similar homes. Use the Flood Risk and Permit lack-of-renovation to argue for additional 'External Obsolescence' and 'Physical Depreciation' adjustments.
        """
        
        prompt = PromptTemplate.from_template(prompt_template)
        # Safety Guard: Ensure vision_data is a list
        visible_issues = []
        if isinstance(vision_data, list):
            # Further protect against non-dict items in list
            visible_issues = [d for d in vision_data if isinstance(d, dict)]
        
        inputs = {
            "address": property_data.get('address', 'N/A'),
            "account_number": property_data.get('account_number', 'N/A'),
            "appraised_value": property_data.get('appraised_value', 0),
            "building_area": property_data.get('building_area', 0),
            "market_value": f"{market_value:,.0f}" if market_value else "N/A",
            "justified_value": f"{equity_data.get('justified_value_floor', 0):,.0f}" if isinstance(equity_data, dict) else "0",
            "comparables": ", ".join([c.get('address', 'N/A') for c in equity_data.get('equity_5', [])]) if isinstance(equity_data, dict) and 'equity_5' in equity_data else "None cited",
            "issues": ", ".join([d.get('issue', 'Unknown') for d in visible_issues]) if visible_issues else "None cited",
            "total_deduction": sum(d.get('deduction', 0) for d in visible_issues) if visible_issues else 0,
            "subject_permits": property_data.get('permit_summary', {}).get('status', 'No major permits found'),
            "comp_renovations": "; ".join([f"{c['address']} has {len(c['renovations'])} major permits" for c in property_data.get('comp_renovations', [])]) or "No major renovations found in comps",
            "flood_zone": property_data.get('flood_zone', 'Zone X (Minimal Risk)')
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
        if self.gemini_llm:
            try:
                logger.info("Attempting narrative generation with Gemini (Fallback)...")
                chain = prompt | self.gemini_llm | StrOutputParser()
                narrative = chain.invoke(inputs)
                return clean_text(narrative)
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
