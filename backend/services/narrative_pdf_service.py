import os
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from fpdf import FPDF
import logging

logger = logging.getLogger(__name__)

class NarrativeAgent:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            try:
                # Configure for 1.5 Flash
                self.llm = ChatGoogleGenerativeAI(
                    model="gemini-1.5-flash", 
                    google_api_key=self.api_key,
                    temperature=0.7
                )
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                self.llm = None
        else:
            self.llm = None

    def generate_protest_narrative(self, property_data: dict, equity_data: dict, vision_data: list) -> str:
        """
        Synthesize Scraper, Equity, and Vision data into a formal protest narrative.
        LCEL Syntax: prompt | llm | output_parser
        """
        if not self.llm:
            return "Narrative Generation Unavailable: GEMINI_API_KEY missing or initialization failed."

        prompt_template = """
        You are an expert Property Tax Consultant in Texas. 
        Write a formal protest narrative for the following property:
        
        Property Details:
        - Address: {address}
        - Account Number: {account_number}
        - Current Appraised Value: ${appraised_value}
        - Building Area: {building_area} sqft
        
        Equity Evidence (Equity 5):
        - Median Justified Value: ${justified_value}
        - Key Comparables: {comparables}
        
        Condition Issues (Vision Agent Detections):
        - Identified Issues: {issues}
        - Total Condition Deduction: ${total_deduction}
        
        The narrative MUST cite:
        - Texas Tax Code §41.43 (Uniform and Equal)
        - Texas Tax Code §41.41 (Market Value)
        
        Structure it professionally for an HCAD Appraisal Review Board (ARB) hearing.
        """
        
        prompt = PromptTemplate.from_template(prompt_template)
        
        # LCEL Chain
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            narrative = chain.invoke({
                "address": property_data.get('address', 'N/A'),
                "account_number": property_data.get('account_number', 'N/A'),
                "appraised_value": property_data.get('appraised_value', 0),
                "building_area": property_data.get('building_area', 0),
                "justified_value": equity_data.get('justified_value_floor', 0),
                "comparables": ", ".join([c['address'] for c in equity_data.get('equity_5', [])]),
                "issues": ", ".join([d['issue'] for d in vision_data]) if vision_data else "None cited",
                "total_deduction": sum(d['deduction'] for d in vision_data)
            })
            return narrative
        except Exception as e:
            logger.error(f"Error in narrative generation: {e}")
            return f"Error generating narrative: {e}"

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
        pdf.multi_cell(0, 10, txt=narrative)
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
