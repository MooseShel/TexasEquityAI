def main():
    with open('backend/services/narrative_pdf_service.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # We need to find the start and end of the block.
    # Start: `# ── PAGE 1B: OUR UNIQUE AI APPROACH`
    start_str = "# ── PAGE 1B: OUR UNIQUE AI APPROACH"
    start_idx = content.find(start_str)
    
    # End: `# ██  APPENDIX: EQUITY COMP GRIDS`
    end_str = "# ██  APPENDIX: EQUITY COMP GRIDS"
    end_idx = content.find(end_str)

    if start_idx == -1 or end_idx == -1:
        print(f"Failed to find start or end index. start={start_idx}, end={end_idx}")
        return

    # Expand start_idx to the beginning of the line
    while start_idx > 0 and content[start_idx-1] not in ('\n', '\r'):
        start_idx -= 1
        
    while end_idx > 0 and content[end_idx-1] not in ('\n', '\r'):
        end_idx -= 1

    body = content[start_idx:end_idx]

    markers = [
        ("METHODOLOGY", "# ── PAGE 1B: OUR UNIQUE AI APPROACH"),
        ("STATS", "# ── NEW: NEIGHBORHOOD STATISTICAL ANALYSIS PAGE"),
        ("SIGNALS", "# ── NEW: EVIDENCE SIGNAL BREAKDOWN PAGE"),  # the header in code was changed to DOCUMENTED ADJUSTMENT FACTORS, but the comment says NEW: EVIDENCE SIGNAL BREAKDOWN PAGE
        ("OBSOLESCENCE", "# ── NEW: EXTERNAL OBSOLESCENCE PAGE"),
        ("ACCOUNT_HISTORY", "# ── PAGE 2: ACCOUNT HISTORY"),
        ("OPINION_OF_VALUE", "# ── PAGE 3: OPINION OF VALUE"),
        ("SALES_GRIDS", "# ── SALES COMP GRIDS"),
        ("EXECUTIVE_SUMMARY", "# ── EXECUTIVE SUMMARY DASHBOARD"),
        ("VALUATION_TREND", "# ── VALUATION TREND & FORECAST"),
        ("PHOTO_COMPARISON", "# ── AI COMP PHOTO COMPARISON"),
        ("FEMA_FLOOD", "# ── FEMA FLOOD ZONE & ENVIRONMENTAL RISK"),
        ("PERMIT_RENOVATION", "# ── PERMIT & RENOVATION CROSS-REFERENCE"),
        ("NEIGHBORHOOD_MARKET", "# ── NEIGHBORHOOD MARKET ANALYSIS"),
        ("COST_APPROACH", "# ██  COST APPROACH VALIDATION"),
        ("PHYSICAL_CONDITION", "# ██  ORIGINAL EVIDENCE PAGES"),
        ("FORMAL_PROTEST", "# ██  FORMAL PROTEST NARRATIVE"),
    ]

    indices = []
    for name, marker in markers:
        idx = body.find(marker)
        if idx != -1:
            # get to start of line
            while idx > 0 and body[idx-1] not in ('\n', '\r'):
                idx -= 1
            indices.append((idx, name))
        else:
            print(f"WARNING: Could not find marker for {name}: {marker}")
    
    indices.sort()
    
    blocks = {}
    for i in range(len(indices)):
        start = indices[i][0]
        end = indices[i+1][0] if i + 1 < len(indices) else len(body)
        name = indices[i][1]
        blocks[name] = body[start:end]

    print(f"Successfully extracted {len(blocks)} blocks.")
    for name in blocks:
        print(f"- {name}: length {len(blocks[name])}")

    target_order = [
        "EXECUTIVE_SUMMARY",
        "FORMAL_PROTEST",
        "OPINION_OF_VALUE",
        "METHODOLOGY",
        "ACCOUNT_HISTORY",
        "VALUATION_TREND",
        "SIGNALS",
        "STATS",
        "NEIGHBORHOOD_MARKET",
        "SALES_GRIDS",
        "COST_APPROACH",
        "PHYSICAL_CONDITION",
        "PHOTO_COMPARISON",
        "OBSOLESCENCE",
        "FEMA_FLOOD",
        "PERMIT_RENOVATION"
    ]

    new_body = ""
    for name in target_order:
        if name in blocks:
            new_body += blocks[name]
        else:
            print(f"ERROR: Target block {name} not found in extracted blocks.")

    new_content = content[:start_idx] + new_body + content[end_idx:]

    with open('backend/services/narrative_pdf_service.py', 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("Successfully wrote new ordered file to narrative_pdf_service.py")


if __name__ == '__main__':
    main()
