"""
Feature Registry — Central catalog of all platform capabilities.

Add new features here and they will automatically appear in:
- The investor/customer pitch deck PDF
- The Streamlit dashboard "About" section
- API documentation

Each feature has: name, category, description, status, and tier.
"""

CATEGORIES = {
    "data": "DATA ACQUISITION & ENRICHMENT",
    "ai": "AI / MACHINE LEARNING ENGINE",
    "enrichment": "ENRICHMENT & INTELLIGENCE LAYERS",
    "report": "REPORT & DELIVERY",
    "innovation": "AI INNOVATIONS (NEW)",
}

# Status: "live", "beta", "planned"
# Tier: 1 = core platform, 2 = differentiator, 3 = innovation
FEATURES = [
    # ── Data Acquisition ──────────────────────────────────────────────
    {"name": "Multi-District Connectors", "category": "data", "tier": 1, "status": "live",
     "short": "HCAD, TAD, CCAD, DCAD, TCAD -- 5 Texas counties",
     "detail": "Live connectors for HCAD, TAD, CCAD, DCAD, TCAD -- covering Houston, Fort Worth, Plano, Dallas, and Austin metro areas. Each connector handles the unique data format and API of its district."},

    {"name": "Bulk Property Database", "category": "data", "tier": 1, "status": "live",
     "short": "600K+ HCAD records pre-loaded",
     "detail": "600K+ HCAD property records with state_class, building details, and valuation history pre-loaded for instant analysis. No waiting for scraping."},

    {"name": "HCAD Live Scraper", "category": "data", "tier": 1, "status": "live",
     "short": "Playwright browser automation for real-time data",
     "detail": "Playwright-powered browser automation extracts real-time data from the HCAD search portal, including valuation history not available in bulk files."},

    {"name": "NonDisclosureBridge", "category": "data", "tier": 1, "status": "live",
     "short": "RentCast + RealEstateAPI fallback for non-disclosure",
     "detail": "Texas is a non-disclosure state. Our bridge layer combines RentCast + RealEstateAPI to estimate sales prices where deed data is unavailable."},

    {"name": "Commercial Enrichment Agent", "category": "data", "tier": 1, "status": "live",
     "short": "Multi-source fallback for commercial properties",
     "detail": "Multi-source fallback chain for commercial properties: RentCast, RealEstateAPI, public records. Handles property types most platforms can't."},

    {"name": "Deed Records Import", "category": "data", "tier": 2, "status": "live",
     "short": "2.4M HCAD deed transfer records",
     "detail": "Bulk-imported deed transfer records from HCAD with sale dates. Enriches every equity comp with verified transaction recency. Last Sale row in every report."},

    # ── AI / ML Engine ────────────────────────────────────────────────
    {"name": "KNN Equity Comp Selection", "category": "ai", "tier": 1, "status": "live",
     "short": "scikit-learn NearestNeighbors with 7 feature dimensions",
     "detail": "scikit-learn NearestNeighbors selects the 5 most comparable properties using 7 feature dimensions: $/sqft, area, year built, grade, neighborhood, and more. Scientifically optimal matches."},

    {"name": "3-Angle Vision Analysis", "category": "ai", "tier": 1, "status": "live",
     "short": "Street View + Gemini/GPT-4o/Grok defect detection",
     "detail": "Google Street View captures at 3 angles. Gemini, GPT-4o, or Grok detects 15+ defect categories: roof, foundation, siding, drainage, landscaping, and structural issues."},

    {"name": "4-Layer Property Type Resolver", "category": "ai", "tier": 1, "status": "live",
     "short": "Automatic residential/commercial/land classification",
     "detail": "Automatically classifies properties as residential, commercial, multi-family, or land using state_class, RentCast, account patterns, and LLM fallback."},

    {"name": "AI Narrative Agent", "category": "ai", "tier": 1, "status": "live",
     "short": "Gemini + OpenAI fallback protest narratives",
     "detail": "Gemini (primary) with OpenAI fallback generates multi-page protest narratives citing Texas Tax Code Sections 23.01, 41.43, and 42.26."},

    {"name": "Professional Valuation Service", "category": "ai", "tier": 1, "status": "live",
     "short": "ARB-format adjustment grid",
     "detail": "Adjustment grid applies per-unit dollar adjustments for age, area, condition, grade, and location differences -- matching ARB hearing format exactly."},

    {"name": "Anomaly Detection Engine", "category": "ai", "tier": 2, "status": "live",
     "short": "Z-score neighborhood outlier detection",
     "detail": "Z-score analysis on Price Per Square Foot across entire neighborhoods. Flags the top outliers and quantifies estimated over-assessment amount."},

    {"name": "AI Condition Delta Scoring", "category": "ai", "tier": 2, "status": "live",
     "short": "Vision AI condition comparison with depreciation",
     "detail": "Vision AI scores subject (1-10) and each comp. Calculates condition delta and translates to depreciation % citing TX Tax Code 23.01."},

    {"name": "XGBoost Win Predictor", "category": "ai", "tier": 2, "status": "live",
     "short": "544K-record HCAD hearing model (82% accuracy, AUC 0.815)",
     "detail": "XGBoost gradient-boosted classifier trained on 544,583 real HCAD ARB hearing outcomes. Hybrid approach blends historical base rate (40%) with 18 property-specific evidence signals (60%) to predict exact win probability."},

    # ── Enrichment & Intelligence ─────────────────────────────────────
    {"name": "FEMA Flood Zone Detection", "category": "enrichment", "tier": 1, "status": "live",
     "short": "Real-time NFHL API flood zone queries",
     "detail": "Real-time NFHL API queries identify properties in high-risk flood zones (A, AE, V, VE). Triggers external obsolescence deduction in the protest."},

    {"name": "Permit Cross-Reference", "category": "enrichment", "tier": 1, "status": "live",
     "short": "Building permit flags for subject + comps",
     "detail": "Cross-checks building permits for both subject and comps. Flags recent renovations that may explain value differences."},

    {"name": "Sales Comp Engine", "category": "enrichment", "tier": 1, "status": "live",
     "short": "RentCast + RealEstateAPI hybrid",
     "detail": "RentCast + RealEstateAPI hybrid fetches and sorts comparable sales by distance and recency. Non-disclosure state handling built-in."},

    {"name": "Cost Approach Analysis", "category": "enrichment", "tier": 1, "status": "live",
     "short": "Marshall & Swift replacement cost benchmark",
     "detail": "Marshall & Swift-based replacement cost calculation provides an independent valuation benchmark beyond equity analysis."},

    {"name": "Market Analysis", "category": "enrichment", "tier": 1, "status": "live",
     "short": "Neighborhood median $/sqft and ratios",
     "detail": "Neighborhood-level median $/sqft, sale-to-assessed ratio, and market health indicators provide context for protest arguments."},

    {"name": "Geo-Intelligence Layer", "category": "enrichment", "tier": 2, "status": "live",
     "short": "Geocoding + external obsolescence detection",
     "detail": "Nominatim + Google geocoding, haversine distance, and external obsolescence detection (highways, industrial, commercial, power infrastructure)."},

    {"name": "Neighborhood Crime Intelligence", "category": "enrichment", "tier": 2, "status": "live",
     "short": "OpenData API real-time crime radius search",
     "detail": "Live API integration (e.g. SODA API) checks violent/property crime incidents within a 0.5-mile radius over 365 days to prove External Obsolescence."},

    # ── Report & Delivery ─────────────────────────────────────────────
    {"name": "Evidence Packet PDF", "category": "report", "tier": 1, "status": "live",
     "short": "1,900-line comprehensive ARB-ready report",
     "detail": "Comprehensive PDF: cover page, methodology, history, equity grid, vision analysis, maps, opinion of value, legal narrative, and appendices."},

    {"name": "Auto-Filled Form 41.44", "category": "report", "tier": 1, "status": "live",
     "short": "Official HCAD protest form pre-populated",
     "detail": "The official HCAD protest form, pre-populated with property data and protest arguments. Ready to file."},

    {"name": "Vision Comp Grid", "category": "report", "tier": 1, "status": "live",
     "short": "Side-by-side AI photo comparison",
     "detail": "Side-by-side AI photo comparison of subject vs. each comp with condition notes and scores."},

    {"name": "ML Win Probability Score", "category": "report", "tier": 1, "status": "live",
     "short": "XGBoost hybrid prediction with explainable factors",
     "detail": "ML-backed exact win probability with explainable breakdown. Shows XGBoost base rate from 544K hearings, evidence adjustments, and top contributing factors."},

    {"name": "4-Year Valuation Trend", "category": "report", "tier": 1, "status": "live",
     "short": "Assessment trajectory chart",
     "detail": "Visual chart showing assessment trajectory, highlighting years of unusual increases."},

    {"name": "QR-Linked Digital Report", "category": "report", "tier": 2, "status": "live",
     "short": "Mobile-optimized interactive dashboard via QR",
     "detail": "Every PDF includes a QR code linking to a mobile-optimized interactive dashboard for digital evidence sharing."},

    # ── Innovations ───────────────────────────────────────────────────
    {"name": "One-Click Neighborhood Scan", "category": "innovation", "tier": 2, "status": "live",
     "short": "Batch scan + click-to-protest UI",
     "detail": "Enter a neighborhood code, instantly analyze ALL properties, rank by over-assessment severity. Click any flagged property to auto-generate a full protest report."},

    {"name": "Mobile-First Report Viewer", "category": "innovation", "tier": 2, "status": "live",
     "short": "Premium mobile dashboard via QR scan",
     "detail": "QR code on every PDF links to an interactive digital dashboard. Homeowners scan with their phone and see: key metrics, savings analysis, anomaly scoring, and full protest narrative."},

    {"name": "Annual Assessment Monitor", "category": "innovation", "tier": 2, "status": "live",
     "short": "Year-over-year tracking with alert thresholds",
     "detail": "Track any property for year-over-year assessment changes. Configurable alert thresholds flag properties where assessments spike. Color-coded dashboard."},
]


def get_features_by_category():
    """Group features by category for display."""
    result = {}
    for cat_key, cat_name in CATEGORIES.items():
        feats = [f for f in FEATURES if f["category"] == cat_key and f["status"] == "live"]
        if feats:
            result[cat_name] = feats
    return result


def get_live_count():
    """Count of live features."""
    return len([f for f in FEATURES if f["status"] == "live"])


def get_innovation_features():
    """Get tier 2+ features for the innovations section."""
    return [f for f in FEATURES if f["tier"] >= 2 and f["status"] == "live"]
