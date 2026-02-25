# Texas Equity AI — UI/UX Improvement Plan

> **Goal:** Modernize the UI, reduce clutter, improve mobile responsiveness, and maintain all important information for the user.

---

## 📋 Executive Summary

The current `frontend/app.py` (2,175 lines) is a powerful tool but suffers from:
1. **Raw JSON dumps** shown to end users (Property tab + Data tab)
2. **No mobile-responsive CSS** — Streamlit's `layout="wide"` breaks on phones/tablets
3. **Crowded sidebar** with too many expanders (5 sections + dividers)
4. **Dense tab layout** with 7 tabs that overwhelm first-time users
5. **Minimal custom styling** — only 1 CSS rule currently (button border-radius)

---

## 🔴 Phase 1: Remove Clutter & Unnecessary Data (Quick Wins)

### 1.1 — Remove Raw JSON on Property Tab ⚠️ HIGH PRIORITY
**Current (line 1448):**
```python
with col1: st.subheader("Details"); st.json(data['property'])
```
**Problem:** Dumps the entire `data['property']` dict as raw JSON — includes internal fields like `comp_renovations`, `vision_detections`, `anomaly_score`, etc. that are meaningless to homeowners.

**Proposed Fix:** Replace with a clean **property details card** showing only user-relevant fields:

| Field | Source Key | Format |
|---|---|---|
| Address | `address` | Plain text |
| Account Number | `account_number` | Plain text |
| District | `district` | Badge/tag |
| Owner | `owner_name` | Plain text |
| Year Built | `year_built` | Plain text |
| Building Area | `building_area` | `X,XXX sq ft` |
| Lot Size | `lot_size` | `X.XX acres` |
| Bedrooms / Baths | `bedrooms` / `bathrooms` | `3 bed / 2 bath` |
| Property Type | `property_type` | Badge (Residential/Commercial) |
| Neighborhood Code | `neighborhood_code` | Plain text |
| Improvement Type | `improvement_type` | Plain text |
| Homestead Exempt | `homestead` | ✅ / ❌ icon |

**Implementation:** Use `st.markdown()` with styled HTML cards or `st.columns()` with `st.metric()`.

### 1.2 — Remove or Hide the "⚙️ Data" Tab ⚠️ HIGH PRIORITY
**Current (line 2174):**
```python
with tab6: st.json(data)
```
**Problem:** Dumps the ENTIRE payload (property + equity + vision + narrative + paths) as raw JSON. This is a debug tool, not a user feature.

**Proposed Fix:** 
- **Option A (Recommended):** Remove `tab6` entirely. Move to a hidden `?debug=true` query param mode.
- **Option B:** Rename to "🔧 Debug" and wrap in `if st.checkbox("Show raw data")` so it defaults to hidden.

**Result:** Reduce from 7 tabs → 6 tabs.

### 1.3 — Consolidate Tabs to Reduce Overwhelm
**Current tabs:** `🏠 Property` | `⚖️ Equity` | `💰 Sales Comps` | `📸 Vision` | `🚨 Intelligence` | `📄 Protest` | `⚙️ Data`

**Proposed tabs (5):**

| New Tab | Contents | Rationale |
|---|---|---|
| **📊 Overview** | Property card + AI Target Value + Assessment History chart | First thing users see — "the summary" |
| **⚖️ Comparables** | Equity analysis + Sales comps (merged) + Maps | Both are comparison data; splitting adds clicks |
| **📸 Condition** | Vision analysis + External obsolescence (merged with Intelligence) | Both relate to property condition/location factors |
| **📄 Protest Packet** | Protest summary + Narrative + PDF download + HCAD form | The action tab — everything needed to file |
| **🔧 Debug** *(hidden by default)* | Raw JSON, only shown when `?debug=true` or checkbox clicked | For power users/developers only |

### 1.4 — Clean Up Sidebar
**Current sidebar sections (top to bottom):**
1. Logo
2. Title + subtitle
3. District selector
4. Manual Override expander
5. Savings Calculator (tax rate slider)
6. Options (force fresh comps checkbox)
7. Neighborhood Anomaly Scan expander
8. Assessment Monitor expander
9. Pitch Deck Generator expander

**Proposed changes:**
- **Keep:** Logo, District, Search input (move from main area), Generate button
- **Collapse "Savings Calculator" + "Options" into one section** — tax rate slider and force-fresh toggle can share space
- **Move "Pitch Deck Generator" to a footer link** — it's a meta/admin action, not a user workflow
- **Keep Anomaly Scan and Assessment Monitor** as sidebar expanders but with cleaner styling

---

## 🟡 Phase 2: Mobile-Responsive Design

### 2.1 — Responsive CSS Foundation
Add a comprehensive CSS block with media queries. Streamlit injects iframes, so we target `.main`, `.block-container`, and Streamlit widget classes.

```css
/* ── Mobile Responsive Overrides ───────────────────────────── */
@media (max-width: 768px) {
    /* Remove wide layout padding */
    .main .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }
    
    /* Stack columns vertically */
    [data-testid="column"] {
        width: 100% !important;
        flex: 100% !important;
        min-width: 100% !important;
    }
    
    /* Reduce metric font sizes */
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
    }
    
    /* Make tabs scrollable */
    .stTabs [data-baseweb="tab-list"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        -webkit-overflow-scrolling: touch;
    }
    .stTabs [data-baseweb="tab"] {
        white-space: nowrap !important;
        font-size: 0.85rem !important;
        padding: 8px 12px !important;
    }
    
    /* Dataframes: horizontal scroll */
    [data-testid="stDataFrame"] {
        overflow-x: auto !important;
    }
    
    /* Maps: full width, reduce height */
    [data-testid="stDeckGlChart"] {
        height: 250px !important;
    }
    
    /* Charts responsive */
    .plotly .main-svg {
        width: 100% !important;
    }
    
    /* Hide sidebar by default on mobile */
    [data-testid="stSidebar"] {
        transform: translateX(-100%);
    }
    
    /* Reduce title size */
    h1 { font-size: 1.5rem !important; }
    h2 { font-size: 1.2rem !important; }
    h3 { font-size: 1.1rem !important; }
}

/* Tablet */
@media (min-width: 769px) and (max-width: 1024px) {
    .main .block-container {
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    [data-testid="column"] {
        min-width: 45% !important;
    }
}
```

### 2.2 — Responsive Data Tables
**Current:** `st.dataframe()` with fixed columns — clips/overflows on mobile.

**Proposed:**
- On mobile, show a **card-based layout** for equity comps instead of a table:
  ```
  ┌─────────────────────────────────┐
  │ 📍 1234 Oak St, Houston TX      │
  │ Appraised: $285,000  │ 2,100ft² │
  │ $/ft²: $135.71  │ Built: 2005   │
  │ Similarity: 94.2%               │
  └─────────────────────────────────┘
  ```
- Use `st.container()` with custom HTML cards for < 768px viewport detection.
- For wider screens, keep the current `st.dataframe()` with formatted columns.

### 2.3 — Touch-Friendly Buttons & Inputs
```css
/* Minimum touch target size (44px per Apple HIG) */
@media (max-width: 768px) {
    .stButton > button {
        min-height: 48px !important;
        font-size: 1rem !important;
    }
    .stTextInput input,
    .stSelectbox select {
        min-height: 44px !important;
        font-size: 16px !important; /* Prevents iOS zoom on focus */
    }
}
```

---

## 🟢 Phase 3: Modern Visual Design

### 3.1 — Custom Theme & Color Palette
Add a Streamlit theme config (`.streamlit/config.toml`) + CSS custom properties:

```toml
[theme]
primaryColor = "#6C63FF"
backgroundColor = "#0E1117"
secondaryBackgroundColor = "#1A1D23"
textColor = "#E8E8E8"
font = "sans serif"
```

**CSS Custom Properties:**
```css
:root {
    --primary: #6C63FF;
    --primary-light: #8B85FF;
    --success: #10B981;
    --warning: #F59E0B;
    --danger: #EF4444;
    --surface: #1A1D23;
    --surface-raised: #21242B;
    --text-primary: #E8E8E8;
    --text-secondary: #9CA3AF;
    --border: rgba(255, 255, 255, 0.08);
    --gradient-primary: linear-gradient(135deg, #6C63FF 0%, #4F46E5 100%);
    --gradient-success: linear-gradient(135deg, #10B981 0%, #059669 100%);
    --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.3);
    --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
}
```

### 3.2 — Premium Property Card (Replace JSON)
Replace the raw JSON dump with a styled card:

```css
.property-card {
    background: var(--surface-raised);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 24px;
    margin-bottom: 16px;
}
.property-card .prop-address {
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 4px;
}
.property-card .prop-meta {
    color: var(--text-secondary);
    font-size: 0.9rem;
}
.property-card .prop-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 16px;
    margin-top: 16px;
}
.prop-grid-item {
    background: var(--surface);
    border-radius: var(--radius-sm);
    padding: 12px;
}
.prop-grid-item label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    display: block;
}
.prop-grid-item .value {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
}
```

### 3.3 — Metric Cards with Gradient Accents
Replace plain `st.metric()` with styled metric cards:

```css
.metric-card {
    background: var(--surface-raised);
    border-radius: var(--radius-md);
    padding: 16px 20px;
    border-left: 4px solid var(--primary);
    box-shadow: var(--shadow-sm);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}
.metric-card.success { border-left-color: var(--success); }
.metric-card.warning { border-left-color: var(--warning); }
.metric-card.danger  { border-left-color: var(--danger); }
```

### 3.4 — Micro-Animations
```css
/* Fade-in for content sections */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
.stTabs [data-baseweb="tab-panel"] {
    animation: fadeInUp 0.3s ease-out;
}

/* Pulse animation for CTA button */
@keyframes subtlePulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(108, 99, 255, 0.4); }
    50% { box-shadow: 0 0 0 8px rgba(108, 99, 255, 0); }
}
.stButton > button[kind="primary"] {
    animation: subtlePulse 2s infinite;
}

/* Smooth transitions for expanders */
[data-testid="stExpander"] {
    transition: all 0.3s ease;
}
```

### 3.5 — Google Font Integration
```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
```

---

## 🔵 Phase 4: Information Architecture Improvements

### 4.1 — Hero Summary Banner (Post-Generation)
After packet generation, show a **hero banner** at top summarizing the result before the tabs:

```
┌──────────────────────────────────────────────────────────┐
│  ✅ Protest Packet Ready                                 │
│                                                          │
│  📍 12345 Main St, Houston TX 77001                      │
│  Account: 0660460360030  │  District: HCAD               │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐           │
│  │ Appraised│  │ AI Target│  │ Est. Savings │           │
│  │ $325,000 │  │ $285,000 │  │ $1,000/yr    │           │
│  └──────────┘  └──────────┘  └──────────────┘           │
│                                                          │
│  [📥 Download Protest Packet]  [📄 View Narrative]       │
└──────────────────────────────────────────────────────────┘
```

This eliminates the need for users to hunt through tabs for the most important info.

### 4.2 — Progressive Disclosure
Instead of showing everything at once:
- **Level 1 (Default):** Hero summary + Overview tab (property + value + chart)
- **Level 2 (Click to expand):** Comparables, Condition details
- **Level 3 (Advanced):** Raw data, HCAD form, debug info

### 4.3 — Inline Help Text
- Replace technical labels with plain-English explanations
- Example: `"Justified Value Floor"` → `"Fair Value (Based on Neighbors)"`
- Example: `"Z-Score"` → `"How Unusual Your Assessment Is"`
- Example: `"External Obsolescence"` → `"Nearby Factors Hurting Your Value"`

---

## 📐 Implementation Priority

| # | Change | Impact | Effort | Priority |
|---|--------|--------|--------|----------|
| 1 | Remove raw JSON from Property tab (1.1) | 🔥 High | Low | **P0** |
| 2 | Remove/hide Data tab (1.2) | 🔥 High | Low | **P0** |
| 3 | Add mobile-responsive CSS (2.1) | 🔥 High | Medium | **P0** |
| 4 | Touch-friendly buttons/inputs (2.3) | High | Low | **P1** |
| 5 | Replace Property tab with clean card (3.2) | High | Medium | **P1** |
| 6 | Consolidate 7 tabs → 5 tabs (1.3) | Medium | High | **P1** |
| 7 | Hero summary banner (4.1) | Medium | Medium | **P1** |
| 8 | Responsive data tables/cards (2.2) | Medium | Medium | **P2** |
| 9 | Custom theme + color palette (3.1) | Medium | Low | **P2** |
| 10 | Google Fonts (3.5) | Low | Low | **P2** |
| 11 | Micro-animations (3.4) | Low | Low | **P3** |
| 12 | Sidebar cleanup (1.4) | Low | Medium | **P3** |
| 13 | Inline help text rewording (4.3) | Low | Low | **P3** |

---

## 🚫 What We Keep (Important Information)

These elements are **essential** and must remain visible:

- ✅ **County Appraised Value** — what the county says your home is worth
- ✅ **AI Target Protest Value** — what we recommend you protest to
- ✅ **Estimated Tax Savings** — bottom-line dollar savings
- ✅ **Equity Comparable Grid** — proof of over-assessment vs neighbors
- ✅ **Sales Comparable Table** — proof from actual sales data
- ✅ **Assessment History Chart** — multi-year trend visualization
- ✅ **Condition Analysis** — vision-detected issues with images
- ✅ **Protest Narrative** — the formal written argument
- ✅ **PDF Download** — the complete evidence packet
- ✅ **Interactive Maps** — geographic context for comparables
- ✅ **Crime/Flood/Obsolescence factors** — external value impacts
- ✅ **HCAD Form Submission** — direct filing capability

---

## 📝 Notes

- All changes are to `frontend/app.py` (Streamlit) + a new `.streamlit/config.toml` for theming
- No backend changes needed — this is purely a presentation layer refactor
- The `?account=XXXXXXXX` QR code mobile viewer (lines 53-185) is already well-designed and should remain as-is
- Streamlit's `layout="wide"` should remain for desktop but CSS overrides handle mobile
- Total estimated implementation time: **4-6 hours** across all phases
