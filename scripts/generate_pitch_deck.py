"""
Texas Equity AI — Investor & Customer Pitch Deck Generator
Generates a professional PDF document showcasing product features,
market positioning, and competitive advantages.
"""

from fpdf import FPDF
import os


def safe_text(text):
    """Replace Unicode characters with ASCII equivalents for FPDF compatibility."""
    if not text:
        return text
    replacements = {
        '\u2014': '--',   # em dash
        '\u2013': '-',    # en dash
        '\u2018': "'",    # left single quote
        '\u2019': "'",    # right single quote  
        '\u201c': '"',    # left double quote
        '\u201d': '"',    # right double quote
        '\u2022': '*',    # bullet
        '\u2026': '...',  # ellipsis
        '\u00ae': '(R)',  # registered
        '\u2122': '(TM)', # trademark
        '\u00a0': ' ',    # nbsp
        '\u2192': '->',   # right arrow
        '\u2190': '<-',   # left arrow
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    # Final fallback: encode to latin-1, replace unknown chars
    return text.encode('latin-1', errors='replace').decode('latin-1')


class PitchDeckPDF(FPDF):
    
    def cell(self, *args, **kwargs):
        if args:
            args = list(args)
            for i, a in enumerate(args):
                if isinstance(a, str):
                    args[i] = safe_text(a)
        for k in kwargs:
            if isinstance(kwargs[k], str):
                kwargs[k] = safe_text(kwargs[k])
        return super().cell(*args, **kwargs)
    
    def multi_cell(self, *args, **kwargs):
        if args:
            args = list(args)
            for i, a in enumerate(args):
                if isinstance(a, str):
                    args[i] = safe_text(a)
        for k in kwargs:
            if isinstance(kwargs[k], str):
                kwargs[k] = safe_text(kwargs[k])
        return super().multi_cell(*args, **kwargs)
    
    # Color palette
    NAVY = (15, 23, 42)        # #0f172a
    DARK_BLUE = (30, 41, 59)   # #1e293b
    SLATE = (51, 65, 85)       # #334155
    ACCENT = (56, 189, 248)    # #38bdf8 sky-400
    GOLD = (250, 204, 21)      # #facc15
    GREEN = (34, 197, 94)      # #22c55e
    WHITE = (255, 255, 255)
    LIGHT_GRAY = (241, 245, 249)
    MED_GRAY = (148, 163, 184)
    RED_ACCENT = (239, 68, 68)
    
    def header(self):
        pass  # Custom per page
    
    def footer(self):
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font('Arial', '', 7)
            self.set_text_color(*self.MED_GRAY)
            self.cell(0, 10, f'Texas Equity AI  |  Confidential  |  Page {self.page_no()}', 0, 0, 'C')
    
    def _dark_bg(self):
        self.set_fill_color(*self.NAVY)
        self.rect(0, 0, 210, 297, 'F')
    
    def _section_header(self, title, subtitle=""):
        self.set_fill_color(*self.DARK_BLUE)
        self.rect(0, 0, 210, 45, 'F')
        self.set_y(12)
        self.set_font('Arial', 'B', 20)
        self.set_text_color(*self.WHITE)
        self.cell(0, 10, title, ln=True, align='C')
        if subtitle:
            self.set_font('Arial', '', 10)
            self.set_text_color(*self.ACCENT)
            self.cell(0, 6, subtitle, ln=True, align='C')
        self.set_y(50)
        self.set_text_color(0, 0, 0)
    
    def _accent_bar(self, y=None):
        if y:
            self.set_y(y)
        self.set_fill_color(*self.ACCENT)
        self.rect(10, self.get_y(), 190, 1, 'F')
        self.ln(4)
    
    def _feature_card(self, icon, title, description, highlight=""):
        x0 = self.get_x()
        y0 = self.get_y()
        
        # Card background
        self.set_fill_color(*self.LIGHT_GRAY)
        self.rect(12, y0, 186, 28, 'F')
        
        # Icon + Title
        self.set_xy(15, y0 + 2)
        self.set_font('Arial', 'B', 11)
        self.set_text_color(*self.DARK_BLUE)
        self.cell(0, 6, f"{icon}  {title}", ln=True)
        
        # Description
        self.set_x(15)
        self.set_font('Arial', '', 8)
        self.set_text_color(*self.SLATE)
        self.multi_cell(178, 4, description)
        
        # Highlight badge
        if highlight:
            self.set_xy(140, y0 + 2)
            self.set_fill_color(*self.GREEN)
            self.set_text_color(*self.WHITE)
            self.set_font('Arial', 'B', 7)
            self.cell(45, 5, highlight, align='C', fill=True)
        
        self.set_y(y0 + 30)
        self.set_text_color(0, 0, 0)
    
    def _stat_row(self, stats):
        """Draw a row of stat cards. stats = [(value, label), ...]"""
        n = len(stats)
        w = 180 / n
        x0 = 15
        y0 = self.get_y()
        
        for i, (val, label) in enumerate(stats):
            x = x0 + i * w
            self.set_fill_color(*self.DARK_BLUE)
            self.rect(x, y0, w - 4, 22, 'F')
            
            self.set_xy(x, y0 + 3)
            self.set_font('Arial', 'B', 16)
            self.set_text_color(*self.ACCENT)
            self.cell(w - 4, 8, str(val), align='C')
            
            self.set_xy(x, y0 + 12)
            self.set_font('Arial', '', 7)
            self.set_text_color(*self.MED_GRAY)
            self.cell(w - 4, 5, label, align='C')
        
        self.set_y(y0 + 28)
        self.set_text_color(0, 0, 0)
    
    def _competitor_row(self, name, features, color=(200, 200, 200)):
        y0 = self.get_y()
        self.set_fill_color(*color)
        self.rect(12, y0, 186, 7, 'F')
        
        self.set_xy(14, y0 + 1)
        self.set_font('Arial', 'B', 7)
        self.set_text_color(*self.DARK_BLUE)
        self.cell(35, 5, name)
        
        self.set_font('Arial', '', 7)
        col_w = 21.5
        for i, feat in enumerate(features):
            self.set_xy(49 + i * col_w, y0 + 1)
            if feat == "YES":
                self.set_text_color(*self.GREEN)
                self.set_font('Arial', 'B', 7)
            elif feat == "NO":
                self.set_text_color(*self.RED_ACCENT)
                self.set_font('Arial', '', 7)
            else:
                self.set_text_color(*self.SLATE)
                self.set_font('Arial', '', 7)
            self.cell(col_w, 5, feat, align='C')
        
        self.set_y(y0 + 8)
        self.set_text_color(0, 0, 0)


def generate_pitch_deck():
    pdf = PitchDeckPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    # ═══════════════════════════════════════════════════════════════════
    # PAGE 1: COVER
    # ═══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf._dark_bg()
    
    # Accent line
    pdf.set_fill_color(*pdf.ACCENT)
    pdf.rect(30, 60, 150, 2, 'F')
    
    # Title block
    pdf.set_y(75)
    pdf.set_font('Arial', 'B', 36)
    pdf.set_text_color(*pdf.WHITE)
    pdf.cell(0, 15, "Texas Equity AI", ln=True, align='C')
    
    pdf.set_font('Arial', '', 14)
    pdf.set_text_color(*pdf.ACCENT)
    pdf.cell(0, 8, "AI-Powered Property Tax Intelligence Platform", ln=True, align='C')
    
    pdf.ln(10)
    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(*pdf.MED_GRAY)
    pdf.cell(0, 7, "The Most Advanced Property Tax Protest Technology in Texas", ln=True, align='C')
    
    # Stats bar
    pdf.ln(15)
    pdf._stat_row([
        ("600K+", "Properties Analyzed"),
        ("2.4M", "Deed Records"),
        ("5", "Counties Covered"),
        ("8", "AI-Powered Features"),
    ])
    
    # Tagline
    pdf.set_y(200)
    pdf.set_fill_color(*pdf.DARK_BLUE)
    pdf.rect(20, 195, 170, 35, 'F')
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(*pdf.GOLD)
    pdf.cell(0, 8, '"The homeowner deserves to see exactly what we found and why."', ln=True, align='C')
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(*pdf.MED_GRAY)
    pdf.cell(0, 6, "Full transparency. No contingency fees. 100% of the savings go to the homeowner.", ln=True, align='C')
    
    # Footer info
    pdf.set_y(255)
    pdf.set_font('Arial', '', 8)
    pdf.set_text_color(*pdf.MED_GRAY)
    pdf.cell(0, 5, "Investor & Product Overview  |  2026", ln=True, align='C')
    pdf.cell(0, 5, "texasequityai.streamlit.app", ln=True, align='C')
    
    # ═══════════════════════════════════════════════════════════════════
    # PAGE 2: THE PROBLEM & OPPORTUNITY
    # ═══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf._section_header("The $73 Billion Problem", "Why Texas Homeowners Are Overtaxed")
    
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(*pdf.SLATE)
    pdf.set_x(15)
    pdf.multi_cell(180, 5,
        "Texas has NO state income tax. Property taxes are the primary revenue source, "
        "averaging 1.8-2.5% of assessed value annually. This creates a system where "
        "appraisal districts have a financial incentive to OVER-assess properties.\n\n"
        "The result? Millions of homeowners pay thousands of dollars more in property "
        "taxes than they should. Most don't know they're over-assessed -- and those who "
        "do often lack the expertise or evidence to successfully protest."
    )
    
    pdf.ln(5)
    pdf._stat_row([
        ("$73B", "TX Property Tax Revenue"),
        ("65%", "Homeowners Don't Protest"),
        ("$1,200", "Avg. Savings per Protest"),
        ("86%", "Protest Success Rate"),
    ])
    
    pdf.ln(3)
    pdf._accent_bar()
    
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(*pdf.DARK_BLUE)
    pdf.set_x(15)
    pdf.cell(0, 8, "The Traditional Approach is Broken", ln=True)
    
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(*pdf.SLATE)
    problems = [
        ("Black-Box Services", "Companies like Ownwell charge 25-35% of savings but never show HOW they found the reduction. Homeowners are in the dark."),
        ("DIY is Overwhelming", "Homeowners who self-protest face 200+ pages of tax code, confusing appraisal data, and ARB panels trained to reject weak evidence."),
        ("One-Size-Fits-All", "Existing tools use generic comparisons without understanding condition, location, or neighborhood-specific factors."),
        ("No Proactive Alerts", "Homeowners only discover over-assessment AFTER they receive their tax bill -- when protest deadlines may have passed."),
    ]
    
    for title, desc in problems:
        pdf.set_x(15)
        pdf.set_font('Arial', 'B', 9)
        pdf.set_text_color(*pdf.RED_ACCENT)
        pdf.cell(0, 5, f"  X  {title}", ln=True)
        pdf.set_x(25)
        pdf.set_font('Arial', '', 8)
        pdf.set_text_color(*pdf.SLATE)
        pdf.multi_cell(170, 4, desc)
        pdf.ln(1)
    
    # ═══════════════════════════════════════════════════════════════════
    # PAGE 3: OUR SOLUTION
    # ═══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf._section_header("Our Solution", "AI That Sees What Humans Miss")
    
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(*pdf.SLATE)
    pdf.set_x(15)
    pdf.multi_cell(180, 5,
        "Texas Equity AI is the only platform that combines computer vision, machine learning, "
        "geo-intelligence, and legal AI to produce ARB-ready evidence packets that win protests. "
        "Every analysis is fully transparent -- homeowners see exactly what we found and why."
    )
    pdf.ln(3)
    
    # Core pillars
    pillars = [
        ("[*]", "Multi-Model AI Engine", "Three AI providers (Gemini, GPT-4o, Grok) analyze every property. If one model misses something, the others catch it. Zero single points of failure.", "TRIPLE REDUNDANCY"),
        ("[V]", "Computer Vision Analysis", "3-angle Street View imagery analyzed for 15+ defect categories: roof deterioration, foundation cracks, siding damage, drainage issues, and more.", "PATENT-PENDING"),
        ("[=]", "KNN Equity Intelligence", "Machine learning selects the 5 most comparable properties using 7 feature dimensions -- not random picks, but scientifically optimal matches.", "ML-POWERED"),
        ("[M]", "Geo-Intelligence Layer", "Automated detection of external obsolescence: highways within 500ft, industrial facilities, flood zones, power infrastructure -- all factors that reduce value.", "AUTOMATED"),
        ("[#]", "Predictive Success Model", "XGBoost ML model trained on 544,583 real HCAD ARB hearing outcomes (82% accuracy). Predicts exact win probability by blending historical base rates with 18 property-specific evidence signals.", "544K RECORDS"),
        ("[D]", "Legal-Grade Output", "ARB-format evidence packet with Texas Tax Code citations, professional adjustment grid, and auto-filled Form 41.44. Ready to present at hearing.", "ARB-READY"),
    ]
    
    for icon, title, desc, badge in pillars:
        pdf._feature_card(icon, title, desc, badge)
    
    # ═══════════════════════════════════════════════════════════════════
    # PAGE 4: COMPLETE PLATFORM CAPABILITIES (FROM REGISTRY)
    # ═══════════════════════════════════════════════════════════════════
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from backend.feature_registry import get_features_by_category, get_live_count, get_innovation_features

    live_count = get_live_count()
    pdf.add_page()
    pdf._section_header("Complete Platform Capabilities", f"{live_count} Production Features -- All Live Today")
    
    features_by_cat = get_features_by_category()
    for cat_name, feats in features_by_cat.items():
        if cat_name.startswith("AI INNOVATION"):
            continue  # Show these on the next page
        
        pdf.set_font('Arial', 'B', 8)
        pdf.set_text_color(*pdf.ACCENT)
        pdf.set_x(12)
        pdf.cell(0, 5, cat_name, ln=True)
        
        for f in feats:
            pdf.set_x(15)
            pdf.set_font('Arial', 'B', 7)
            pdf.set_text_color(*pdf.DARK_BLUE)
            pdf.cell(48, 4, f["name"])
            pdf.set_font('Arial', '', 7)
            pdf.set_text_color(*pdf.SLATE)
            pdf.cell(0, 4, f["short"][:110], ln=True)
        
        pdf.ln(2)
        
        if pdf.get_y() > 260:
            pdf.add_page()
            pdf._section_header("Platform Capabilities", "Continued")
    
    # ═══════════════════════════════════════════════════════════════════
    # PAGE 5-6: AI INNOVATIONS (DYNAMIC FROM REGISTRY)
    # ═══════════════════════════════════════════════════════════════════
    innovations = get_innovation_features()
    pdf.add_page()
    pdf._section_header(f"{len(innovations)} AI Innovations", "Intelligence Layers Built This Quarter")
    
    for idx, f in enumerate(innovations):
        y0 = pdf.get_y()
        if y0 > 240:
            pdf.add_page()
            pdf._section_header(f"{len(innovations)} AI Innovations", "Continued")
            y0 = pdf.get_y()
        
        num = str(idx + 1)
        pdf.set_fill_color(*pdf.ACCENT)
        pdf.rect(14, y0, 10, 10, 'F')
        pdf.set_xy(14, y0 + 1.5)
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(*pdf.WHITE)
        pdf.cell(10, 7, num, align='C')
        
        pdf.set_xy(28, y0)
        pdf.set_font('Arial', 'B', 10)
        pdf.set_text_color(*pdf.DARK_BLUE)
        pdf.cell(170, 6, f["name"], ln=True)
        pdf.set_x(28)
        pdf.set_font('Arial', '', 8)
        pdf.set_text_color(*pdf.SLATE)
        pdf.multi_cell(168, 4, f["detail"])
        pdf.ln(4)
    
    # ═══════════════════════════════════════════════════════════════════
    # PAGE 6: COMPETITIVE ADVANTAGE
    # ═══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf._section_header("Competitive Advantage", "Why We Win Against $50M+ Funded Competitors")
    
    # Header row
    y0 = pdf.get_y()
    pdf.set_fill_color(*pdf.NAVY)
    pdf.rect(12, y0, 186, 7, 'F')
    pdf.set_xy(14, y0 + 1)
    pdf.set_font('Arial', 'B', 7)
    pdf.set_text_color(*pdf.WHITE)
    pdf.cell(35, 5, "Feature")
    
    headers = ["AI Vision", "ML Comps", "Anomaly", "Geo-Intel", "Predictor", "Savings", "Transparent"]
    col_w = 21.5
    for i, h in enumerate(headers):
        pdf.set_xy(49 + i * col_w, y0 + 1)
        pdf.cell(col_w, 5, h, align='C')
    pdf.set_y(y0 + 8)
    
    # Data rows
    competitors = [
        ("Texas Equity AI", ["YES", "YES", "YES", "YES", "YES", "YES", "YES"], pdf.LIGHT_GRAY),
        ("Ownwell ($50M)", ["NO", "Partial", "NO", "NO", "NO", "YES", "NO"], pdf.WHITE),
        ("PropertyTax.io", ["NO", "Partial", "NO", "NO", "NO", "YES", "NO"], pdf.LIGHT_GRAY),
        ("TX Tax Protest", ["NO", "NO", "NO", "NO", "NO", "Partial", "NO"], pdf.WHITE),
        ("Smart Appeal AI", ["NO", "Partial", "NO", "NO", "NO", "NO", "Partial"], pdf.LIGHT_GRAY),
        ("AppealEdge", ["NO", "Partial", "NO", "NO", "NO", "NO", "YES"], pdf.WHITE),
        ("DIY (Homeowner)", ["NO", "NO", "NO", "NO", "NO", "NO", "YES"], pdf.LIGHT_GRAY),
    ]
    
    for name, feats, color in competitors:
        pdf._competitor_row(name, feats, color)
    
    pdf.ln(5)
    pdf._accent_bar()
    
    # 3 Competitive moats
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(*pdf.DARK_BLUE)
    pdf.set_x(15)
    pdf.cell(0, 8, "Our Three Unfair Advantages", ln=True)
    pdf.ln(2)
    
    moats = [
        ("1. Transparency", "Every competitor is a black box. We show the homeowner exactly what our AI found, which comps were selected, why the condition delta matters, and the specific Tax Code sections that support the argument. This builds trust and converts at 3x the rate of opaque services."),
        ("2. Multi-AI Redundancy", "We run Gemini, GPT-4o, and Grok in parallel. If Google's model misses a roof defect, OpenAI catches it. If OpenAI hallucinates a comp, Gemini validates. This triple-check architecture is unique in the industry."),
        ("3. Data Depth", "600K+ bulk property records, 2.4M deed transfers, 5 county connectors, and multiple enrichment APIs. Most competitors rely on a single data source. Our multi-source approach means more accurate comps, better anomaly detection, and stronger evidence."),
    ]
    
    for title, desc in moats:
        pdf.set_x(15)
        pdf.set_font('Arial', 'B', 9)
        pdf.set_text_color(*pdf.ACCENT)
        pdf.cell(0, 5, title, ln=True)
        pdf.set_x(15)
        pdf.set_font('Arial', '', 8)
        pdf.set_text_color(*pdf.SLATE)
        pdf.multi_cell(180, 4, desc)
        pdf.ln(2)
    
    # ═══════════════════════════════════════════════════════════════════
    # PAGE 7: TECHNOLOGY STACK
    # ═══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf._section_header("Technology Stack", "Enterprise-Grade Architecture")
    
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(*pdf.SLATE)
    pdf.set_x(15)
    pdf.multi_cell(180, 4,
        "Built on modern, scalable infrastructure with security-first design. "
        "Row-Level Security (RLS) on all database tables. Multi-tenant ready."
    )
    pdf.ln(3)
    
    stack_categories = [
        ("AI / Machine Learning", [
            "Google Gemini 2.0 Flash -- Primary vision & narrative AI",
            "OpenAI GPT-4o -- Fallback vision & analysis",
            "xAI Grok -- Third-layer validation",
            "XGBoost -- Protest outcome predictor trained on 544K HCAD hearings (82% acc)",
            "scikit-learn KNN -- Equity comp selection algorithm",
            "NumPy / Pandas -- Statistical analysis engine",
        ]),
        ("Backend Infrastructure", [
            "FastAPI -- High-performance async Python backend",
            "Supabase (PostgreSQL) -- Managed database with RLS",
            "Playwright -- Browser automation for live data scraping",
            "Google Maps API -- Street View, geocoding, Places",
            "Nominatim (OSM) -- Free geocoding with zero API cost",
        ]),
        ("Data Sources", [
            "HCAD, TAD, CCAD, DCAD, TCAD -- 5 Texas county connectors",
            "RentCast + RealEstateAPI -- Sales comp enrichment",
            "FEMA NFHL -- Flood zone detection",
            "County deed records -- 2.4M transfer records",
        ]),
        ("Frontend & Delivery", [
            "Streamlit -- Interactive web dashboard",
            "FPDF2 -- Professional PDF evidence packet generation",
            "QR Code -- Mobile-first report access",
            "Responsive CSS -- Phone-optimized report viewer",
        ]),
    ]
    
    for category, items in stack_categories:
        pdf.set_font('Arial', 'B', 10)
        pdf.set_text_color(*pdf.DARK_BLUE)
        pdf.set_x(15)
        pdf.cell(0, 6, category, ln=True)
        
        for item in items:
            pdf.set_font('Arial', '', 8)
            pdf.set_text_color(*pdf.SLATE)
            pdf.set_x(20)
            pdf.cell(0, 4, f"   {item}", ln=True)
        pdf.ln(2)
    
    # ═══════════════════════════════════════════════════════════════════
    # PAGE 8: MARKET OPPORTUNITY & REVENUE MODEL
    # ═══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf._section_header("Market Opportunity", "A $4.2B Addressable Market in Texas Alone")
    
    pdf._stat_row([
        ("7.2M", "TX Homeowners"),
        ("$4.2B", "TAM (Texas)"),
        ("$18B", "TAM (US)"),
        ("23%", "CAGR PropTech"),
    ])
    
    pdf.ln(3)
    pdf._accent_bar()
    
    # Revenue model
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(*pdf.DARK_BLUE)
    pdf.set_x(15)
    pdf.cell(0, 8, "Revenue Model", ln=True)
    pdf.ln(2)
    
    models = [
        ("B2C: Individual Reports", "$29-49 per report", "Homeowners generate their own evidence. No contingency fees -- they keep 100% of savings. At avg. $1,200 savings, ROI is 24-41x."),
        ("B2B: Tax Consultant License", "$199-499/mo", "Unlimited neighborhood scans, batch processing, white-label reports. One consultant with 200 clients = $60K-120K in annual protest savings."),
        ("B2B2C: Brokerage Integration", "Revenue share", "Real estate brokers offer protest analysis as a value-add. \"Buy this home, and we'll protest your taxes every year.\""),
        ("SaaS: Assessment Monitor", "$9.99/mo per property", "Annual subscription for assessment tracking and alerts. Recurring revenue with minimal marginal cost."),
    ]
    
    for title, price, desc in models:
        y0 = pdf.get_y()
        pdf.set_fill_color(*pdf.LIGHT_GRAY)
        pdf.rect(12, y0, 186, 18, 'F')
        
        pdf.set_xy(15, y0 + 1)
        pdf.set_font('Arial', 'B', 9)
        pdf.set_text_color(*pdf.DARK_BLUE)
        pdf.cell(100, 5, title)
        
        pdf.set_xy(130, y0 + 1)
        pdf.set_font('Arial', 'B', 9)
        pdf.set_text_color(*pdf.GREEN)
        pdf.cell(65, 5, price, align='R')
        
        pdf.set_xy(15, y0 + 7)
        pdf.set_font('Arial', '', 8)
        pdf.set_text_color(*pdf.SLATE)
        pdf.multi_cell(178, 4, desc)
        
        pdf.set_y(y0 + 20)
    
    # ═══════════════════════════════════════════════════════════════════
    # PAGE 9: THE EVIDENCE PACKET (WHAT THE CUSTOMER GETS)
    # ═══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf._section_header("The Evidence Packet", "What Every Homeowner Receives")
    
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(*pdf.SLATE)
    pdf.set_x(15)
    pdf.multi_cell(180, 5,
        "Each protest generates a comprehensive, ARB-ready evidence packet. "
        "This is what sets us apart -- no other platform produces this level of detail."
    )
    pdf.ln(3)
    
    sections = [
        ("Cover Page", "Property summary with anomaly badge, protest viability score, estimated savings range, and QR code linking to the interactive digital report."),
        ("AI Methodology Page", "Explains the multi-model AI approach, building trust with ARB panels and homeowners alike."),
        ("Account History", "Owner info, property details, 4-year valuation trend chart showing assessment trajectory."),
        ("Equity Comparison Grid", "5 ML-selected comparables with: address, value, $/sqft, year built, last sale date, condition score, and distance from subject."),
        ("AI Vision Analysis", "Side-by-side 3-angle Street View photos with AI-detected defects marked."),
        ("Geo-Intelligence Map", "Static map showing subject and comp locations with distances."),
        ("Opinion of Value", "AI-generated justified value with supporting calculations and savings prediction."),
        ("Legal Narrative", "Multi-page protest citing Texas Tax Code Sections 23.01, 41.43(b)(1), and 42.26."),
        ("Appendices", "FEMA flood zone data, permit cross-reference, cost approach analysis."),
    ]
    
    for title, desc in sections:
        pdf.set_x(15)
        pdf.set_font('Arial', 'B', 9)
        pdf.set_text_color(*pdf.ACCENT)
        pdf.cell(0, 5, f"  >>  {title}", ln=True)
        pdf.set_x(25)
        pdf.set_font('Arial', '', 8)
        pdf.set_text_color(*pdf.SLATE)
        pdf.multi_cell(170, 4, desc)
        pdf.ln(1)
    
    # ═══════════════════════════════════════════════════════════════════
    # PAGE 10: CALL TO ACTION
    # ═══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf._dark_bg()
    
    pdf.set_fill_color(*pdf.ACCENT)
    pdf.rect(30, 50, 150, 2, 'F')
    
    pdf.set_y(65)
    pdf.set_font('Arial', 'B', 28)
    pdf.set_text_color(*pdf.WHITE)
    pdf.cell(0, 12, "Ready to Transform", ln=True, align='C')
    pdf.cell(0, 12, "Property Tax Protests?", ln=True, align='C')
    
    pdf.ln(10)
    pdf.set_font('Arial', '', 12)
    pdf.set_text_color(*pdf.ACCENT)
    pdf.cell(0, 8, "Texas Equity AI delivers what no other platform can:", ln=True, align='C')
    
    pdf.ln(8)
    highlights = [
        "AI-powered evidence that wins 86%+ of protests",
        "Complete transparency -- homeowners see everything",
        "No contingency fees -- 100% of savings stay with the homeowner",
        "5 counties live, with nationwide expansion ready",
        "8 AI features, all production-ready today",
    ]
    
    for h in highlights:
        pdf.set_font('Arial', '', 11)
        pdf.set_text_color(*pdf.WHITE)
        pdf.cell(0, 8, f"   {h}", ln=True, align='C')
    
    pdf.ln(15)
    pdf.set_fill_color(*pdf.DARK_BLUE)
    pdf.rect(30, pdf.get_y(), 150, 40, 'F')
    y_box = pdf.get_y()
    
    pdf.set_y(y_box + 5)
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(*pdf.GOLD)
    pdf.cell(0, 8, "Let's Talk", ln=True, align='C')
    
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(*pdf.WHITE)
    pdf.cell(0, 6, "texasequityai.streamlit.app", ln=True, align='C')
    pdf.cell(0, 6, "Schedule a demo or start your free analysis today", ln=True, align='C')
    
    pdf.set_y(265)
    pdf.set_font('Arial', '', 8)
    pdf.set_text_color(*pdf.MED_GRAY)
    pdf.cell(0, 5, "CONFIDENTIAL  |  Texas Equity AI  |  2026", ln=True, align='C')
    
    # Save
    os.makedirs("outputs", exist_ok=True)
    output_path = "outputs/Texas_Equity_AI_Pitch_Deck.pdf"
    pdf.output(output_path)
    return output_path


if __name__ == "__main__":
    path = generate_pitch_deck()
    print(f"Pitch deck generated: {path}")
