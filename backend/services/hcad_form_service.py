from fpdf import FPDF
import os
import datetime
import random
from backend.services.narrative_pdf_service import clean_text

class HCADFormService:
    def generate_form_41_44(self, property_data: dict, protest_data: dict, output_path: str):
        """
        Generates a comprehensive property tax protest report including a cover page,
        HCAD Form 41.44 summary, equity evidence grid, and photographic evidence.
        """
        pdf = FPDF()
        
        # --- PAGE 1: COVER PAGE ---
        pdf.add_page()
        pdf.set_fill_color(30, 41, 59) # Dark Slate Blue
        pdf.rect(0, 0, 210, 297, 'F') # Full page background
        
        # Title
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", 'B', 28)
        pdf.ln(60)
        pdf.cell(0, 15, "PROPERTY ANALYSIS", ln=True, align='C')
        pdf.set_font("Helvetica", 'B', 32)
        pdf.cell(0, 15, "EVIDENCE PACKET", ln=True, align='C')
        
        pdf.ln(10)
        pdf.set_font("Helvetica", '', 14)
        pdf.cell(0, 10, "Tax Year 2025 Protest Submission", ln=True, align='C')
        
        # Blue accent line
        pdf.set_draw_color(59, 130, 246)
        pdf.set_line_width(1)
        pdf.line(40, 115, 170, 115)
        
        pdf.ln(30)
        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(0, 10, "SUBJECT PROPERTY:", ln=True, align='C')
        pdf.set_font("Helvetica", '', 14)
        pdf.cell(0, 10, f"{clean_text(property_data.get('address', 'Unknown Address'))}", ln=True, align='C')
        pdf.cell(0, 10, f"Account #: {property_data.get('account_number', 'N/A')}", ln=True, align='C')
        
        # Info Box at Bottom
        pdf.set_y(240)
        pdf.set_font("Helvetica", 'B', 10)
        case_id = f"TX-REQ-{random.randint(10000, 99999)}"
        timestamp = datetime.datetime.now().strftime("%B %d, %Y")
        
        pdf.cell(0, 6, f"CASE ID: {case_id}", ln=True, align='C')
        pdf.cell(0, 6, f"Generated On: {timestamp}", ln=True, align='C')
        pdf.cell(0, 6, "Prepared for Harris County Appraisal Review Board", ln=True, align='C')
        
        # --- PAGE 2: FORM 41.44 SUMMARY ---
        pdf.add_page()
        pdf.set_text_color(0, 0, 0) # Reset to black
        
        # Header
        pdf.set_font("Helvetica", 'B', 16)
        pdf.cell(0, 10, "Form 41.44: Property Tax Notice of Protest (Summary)", ln=True, align='C')
        pdf.set_font("Helvetica", size=10)
        pdf.cell(0, 10, "Appraisal Review Board for the Harris Central Appraisal District", ln=True, align='C')
        pdf.ln(10)
        
        # Section 1: Property Description
        pdf.set_fill_color(240, 244, 255) # Light blue header
        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(0, 10, " STEP 1: Property Description ", ln=True, fill=True)
        pdf.set_font("Helvetica", size=10)
        pdf.cell(0, 8, f"Account Number: {property_data.get('account_number')}", ln=True)
        pdf.cell(0, 8, f"Property Address: {clean_text(property_data.get('address', ''))}", ln=True)
        pdf.ln(5)
        
        # Section 2: Reason for Protest
        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(0, 10, " STEP 2: Reason for Protest ", ln=True, fill=True)
        pdf.set_font("Helvetica", size=10)
        pdf.cell(0, 8, "[X] Incorrect appraised (market) value", ln=True)
        pdf.cell(0, 8, "[X] Value is unequal compared with other properties (Equity)", ln=True)
        
        vision_detected = len(protest_data.get('vision_data', [])) > 0
        condition_check = "[X]" if vision_detected else "[ ]"
        pdf.cell(0, 8, f"{condition_check} Property condition (Physical damage/defects)", ln=True)
        pdf.ln(5)
        
        # Section 3: Evidence Summary
        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(0, 10, " STEP 3: Evidence & Narrative Summary ", ln=True, fill=True)
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, txt=clean_text(protest_data.get('narrative', 'N/A')))
        pdf.ln(5)

        # --- PAGE 3: EQUITY EVIDENCE GRID ---
        equity_data = protest_data.get('equity_results')
        if equity_data and 'equity_5' in equity_data:
            pdf.add_page()
            pdf.set_font("Helvetica", 'B', 14)
            pdf.cell(0, 10, "COMPARATIVE EQUITY ANALYSIS GRID", ln=True, align='C')
            pdf.set_font("Helvetica", '', 10)
            pdf.cell(0, 8, "The following 5 properties are structurally similar and geographically proximate.", ln=True, align='C')
            pdf.ln(5)
            
            # Table Header
            pdf.set_font("Helvetica", 'B', 9)
            pdf.set_fill_color(240, 240, 240)
            col_widths = [70, 30, 30, 30, 30]
            headers = ["Comparable Address", "Appraised Val", "Sq Ft", "$/SqFt", "Similarity"]
            
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 8, h, 1, 0, 'C', True)
            pdf.ln()

            # Table Rows
            pdf.set_font("Helvetica", size=9)
            for comp in equity_data['equity_5']:
                addr = clean_text(comp.get('address', 'N/A'))
                val = comp.get('appraised_value', 0)
                area = comp.get('building_area', 1) # Avoid div by zero if any
                vps = comp.get('value_per_sqft', val/area if area > 0 else 0)
                sim = comp.get('similarity_score', 0)
                
                pdf.cell(col_widths[0], 8, addr, 1, 0, 'L')
                pdf.cell(col_widths[1], 8, f"${val:,.0f}", 1, 0, 'C')
                pdf.cell(col_widths[2], 8, f"{area:,.0f}", 1, 0, 'C')
                pdf.cell(col_widths[3], 8, f"${vps:.2f}", 1, 0, 'C')
                pdf.cell(col_widths[4], 8, f"{sim:.2f}", 1, 1, 'C')
            
            pdf.ln(10)
            pdf.set_fill_color(255, 240, 240)
            pdf.set_font("Helvetica", 'B', 11)
            pdf.cell(130, 10, "JUSTIFIED VALUE PER EQUITY (Floor Analysis)", 1, 0, 'R')
            justified_val = equity_data.get('justified_value_floor', 0)
            pdf.cell(60, 10, f"${justified_val:,.0f}", 1, 1, 'C', True)

        # --- PAGE 4: PHOTOGRAPHIC EVIDENCE ---
        pdf.add_page()
        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(0, 10, " STEP 4: Condition Analysis & Photographic Evidence ", ln=True, fill=True)
        pdf.ln(5)
        
        evidence_image_path = protest_data.get('evidence_image_path')
        if evidence_image_path and os.path.exists(evidence_image_path):
            try:
                pdf.image(evidence_image_path, x=20, w=170)
                pdf.ln(5)
                pdf.set_y(pdf.get_y() + 115) 
            except Exception as e:
                pdf.cell(0, 10, f"Error embedding image: {str(e)}", ln=True)
        
        # Detected Issues Table
        vision_data = protest_data.get('vision_data', [])
        # Safety guard: ensure it's a list of dicts
        if isinstance(vision_data, list) and len(vision_data) > 0:
            valid_issues = [i for i in vision_data if isinstance(i, dict)]
            if valid_issues:
                pdf.set_font("Helvetica", 'B', 10)
                pdf.set_fill_color(248, 248, 248)
                pdf.cell(60, 8, "Condition Issue", 1, 0, 'L', True)
                pdf.cell(100, 8, "Visual Observation", 1, 0, 'L', True)
                pdf.cell(30, 8, "Deduction", 1, 1, 'R', True)
                
                pdf.set_font("Helvetica", size=9)
                for issue in valid_issues:
                    name = clean_text(issue.get('issue', 'Unknown'))
                    desc = clean_text(issue.get('description', 'Visual defect detected'))
                    deduct = issue.get('deduction', 0)
                    
                    # Store current Y to draw the border later
                    start_y = pdf.get_y()
                    
                    # Column 1
                    pdf.set_xy(10, start_y)
                    pdf.multi_cell(60, 10, name, border=1)
                    end_y1 = pdf.get_y()
                    
                    # Column 2
                    pdf.set_xy(70, start_y)
                    pdf.multi_cell(100, 10, desc, border=1)
                    end_y2 = pdf.get_y()
                    
                    # Column 3
                    pdf.set_xy(170, start_y)
                    pdf.multi_cell(30, 10, f"-${deduct:,}", border=1, align='R')
                    end_y3 = pdf.get_y()
                    
                    # Set Y to the max height of the row
                    pdf.set_y(max(end_y1, end_y2, end_y3))

        # Footer / Signature
        pdf.set_y(260)
        pdf.set_font("Helvetica", 'I', 8)
        pdf.cell(0, 10, "Signature: __________________________________________    Date: ____________________", ln=True, align='C')
        pdf.cell(0, 10, "Generated by Texas Equity AI. This is a computer-aided protest evidence packet.", ln=True, align='C')
        
        pdf.output(output_path)
        return output_path
