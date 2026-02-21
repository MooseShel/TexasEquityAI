import os

filepath = r"c:\Users\Husse\Documents\TexasEquityAI\backend\services\narrative_pdf_service.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Modify Matplotlib chart colors
# Old Appraised (blue): #3b82f6
# Old Market (green): #10b981
content = content.replace("color='#3b82f6'", "color='#1d4ed8'") # Darker Sapphire Blue
content = content.replace("color='#10b981'", "color='#059669'") # Richer Emerald Green

# Update FPDF Executive Summary Method colors (red/yellow/green alerts)
# Red: 239, 68, 68
# Yellow: 251, 191, 36
# Green: 34, 197, 94
# Change to slightly more polished tones
content = content.replace("239, 68, 68", "220, 38, 38") # Red-600
content = content.replace("251, 191, 36", "217, 119, 6") # Amber-600
content = content.replace("34, 197, 94", "5, 150, 105") # Emerald-600

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Chart and dashboard badge colors refined.")
