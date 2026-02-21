import re
import os

filepath = r"c:\Users\Husse\Documents\TexasEquityAI\backend\services\narrative_pdf_service.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update font adding in generate_evidence_packet
font_loader = """
        pdf = FPDF()
        
        # Load Premium Fonts
        try:
            fonts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
            pdf.add_font("Montserrat", "", os.path.join(fonts_dir, "Montserrat-Regular.ttf"))
            pdf.add_font("Montserrat", "B", os.path.join(fonts_dir, "Montserrat-Bold.ttf"))
            pdf.add_font("Montserrat", "I", os.path.join(fonts_dir, "Montserrat-Italic.ttf"))
            
            pdf.add_font("Roboto", "", os.path.join(fonts_dir, "Roboto-Regular.ttf"))
            pdf.add_font("Roboto", "B", os.path.join(fonts_dir, "Roboto-Bold.ttf"))
            pdf.add_font("Roboto", "I", os.path.join(fonts_dir, "Roboto-Italic.ttf"))
            
            BODY_FONT = "Roboto"
            TITLE_FONT = "Montserrat"
        except Exception as e:
            logger.warning(f"Failed to load custom fonts: {e}")
            BODY_FONT = "Arial"
            TITLE_FONT = "Arial"
"""
content = content.replace("        pdf = FPDF()", font_loader)

# Replace globally Arial with BODY_FONT, except for headers which get TITLE_FONT
# We'll just replace literal "Arial" with BODY_FONT to start.
# Note: since it's a variable, we have to drop the quotes.
# Wait, FPDF expects a string. If we set BODY_FONT as string, we shouldn't replace "Arial" with '"Roboto"' directly inside class methods unless they access self.BODY_FONT.
# Let's make it a class-level or service-level variable, but we can't easily do it if it's dynamic.
# Actually, just replacing "Arial" with "Roboto", because we know Roboto will be registered.
content = content.replace('"Arial"', '"Roboto"')
content = content.replace("'Arial'", '"Roboto"')

# 2. Update specific Headers to Montserrat
# Example: pdf.set_font("Roboto", 'B', 32) -> Montserrat
content = re.sub(r'pdf\.set_font\("Roboto",\s*\'B\',\s*32\)', r'pdf.set_font("Montserrat", \'B\', 32)', content)
content = re.sub(r'pdf\.set_font\("Roboto",\s*\'B\',\s*36\)', r'pdf.set_font("Montserrat", \'B\', 36)', content)
content = re.sub(r'pdf\.set_font\("Roboto",\s*\'B\',\s*14\)', r'pdf.set_font("Montserrat", \'B\', 14)', content)
content = re.sub(r'pdf\.set_font\("Roboto",\s*\'B\',\s*12\)', r'pdf.set_font("Montserrat", \'B\', 12)', content)
content = re.sub(r'pdf\.set_font\("Roboto",\s*\'B\',\s*28\)', r'pdf.set_font("Montserrat", \'B\', 28)', content)
content = re.sub(r'pdf\.set_font\("Roboto",\s*\'B\',\s*20\)', r'pdf.set_font("Montserrat", \'B\', 20)', content)

# 3. Update Colors
# Navy: (30, 41, 59) -> (10, 25, 47)
content = content.replace("30, 41, 59", "10, 25, 47")

# Sapphire Blue: (59, 130, 246) -> (29, 78, 216)
content = content.replace("59, 130, 246", "29, 78, 216")

# Light gray table header background: (220, 225, 235) -> (241, 245, 249)
content = content.replace("220, 225, 235", "241, 245, 249")
# Light fill color rows: (245, 245, 250) -> (248, 250, 252)
content = content.replace("245, 245, 250", "248, 250, 252")


# 4. Update Tables (remove vertical borders, use 'B' and increase height)
# In _table_header: pdf.cell(widths[i], 7, clean_text(h), 1, 0, 'C', True)
# We change 7 to 9 (height), and 1 to 'B'.
content = re.sub(r'pdf\.cell\(widths\[i\],\s*7,\s*clean_text\(h\),\s*1,\s*0,\s*\'C\',\s*True\)', 
                 r"pdf.cell(widths[i], 9, clean_text(h), 'B', 0, 'C', True)", content)

# In _table_row: pdf.cell(widths[i], 7, text_val, 1, 0, cell_align, fill)
# We will intercept the text_val to align right if it's a number/currency and change height to 9, border to 'B'.
new_table_row = '''
            # Check if value is numeric or currency
            if isinstance(v, (int, float)) or (isinstance(v, str) and (v.startswith("$") or v.endswith("%"))):
                curr_align = 'R'
            else:
                curr_align = cell_align
            # Also apply subtle bottom border
            pdf.cell(widths[i], 9, text_val, 'B', 0, curr_align, fill)
'''
content = re.sub(r'pdf\.cell\(widths\[i\],\s*7,\s*text_val,\s*1,\s*0,\s*cell_align,\s*fill\)', new_table_row.strip(), content)

# Update row alignments for other tables directly using 1 -> 'B' or '0' (no border)
# e.g., pdf.cell(vb_w[0], 7, self._fmt(subj_land) if subj_land else "See History", 1, 0, 'C')
content = content.replace(", 1, 0, 'C')", ", 'B', 0, 'C')")
content = content.replace(", 1, 0, 'L', True)", ", 'B', 0, 'L', True)")
content = content.replace(", 1, 0, 'C', True)", ", 'B', 0, 'C', True)")
content = content.replace(", 1, 1, 'L', True)", ", 'B', 1, 'L', True)")


# 5. Fix _draw_header
# Make it look more premium
header_replacement = '''
    def _draw_header(self, pdf, property_data, title):
        pdf.set_fill_color(10, 25, 47)
        pdf.rect(0, 0, 210, 28, 'F')
        pdf.set_xy(10, 6)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Montserrat", 'B', 14)
        pdf.cell(0, 8, clean_text(title), ln=True)
        pdf.set_font("Roboto", '', 9)
        pdf.set_text_color(200, 210, 220)
        pdf.cell(0, 5, clean_text(f"Property: {property_data.get('address')}  |  Account: {property_data.get('account_number')}"), ln=True)
        pdf.set_text_color(0, 0, 0)
        # Subtle bottom accent line
        pdf.set_draw_color(29, 78, 216)
        pdf.set_line_width(0.8)
        pdf.line(0, 28, 210, 28)
        pdf.set_draw_color(200, 200, 200) # Reset
        pdf.set_line_width(0.2)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_y(35)
'''
# Using regex to replace the old _draw_header entirely
content = re.sub(r'    def _draw_header\(self, pdf, property_data, title\):.*?(?=    # ── Map Generation)', header_replacement, content, flags=re.DOTALL)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("PDF Aesthetics Updated Successfully.")
