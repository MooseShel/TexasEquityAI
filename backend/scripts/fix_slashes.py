import re

filepath = r"c:\Users\Husse\Documents\TexasEquityAI\backend\services\narrative_pdf_service.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the backslash quotes
content = content.replace(r"\'", "'")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed")
