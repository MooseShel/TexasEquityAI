# Texas Equity AI: Data Foundation & Competitive Roadmap

This document outlines the strategic datasets that provide a competitive advantage for property tax protests in Harris County, Texas.

## 1. Building Permit History
*   **Source**: City of Houston / Harris County Permit Portals (Public Record).
*   **The Advantage**: Identifies major renovations in neighboring "comparable" properties.
*   **The Argument**: If a comparable has a major renovation permit and the subject property does not, the comparable's value should be adjusted downward for "superior condition," lowering the equity floor for the subject property.
*   **Status**: COMPLETE - Integrated via City of Houston CKAN API.

## 2. FEMA Flood Zone & Elevation Data
*   **Source**: FEMA National Flood Hazard Layer (NFHL) / Harris County Flood Control District (GIS).
*   **The Advantage**: Quantifies locational risk and insurance burden.
*   **The Argument**: Properties in high-risk flood zones (Zone AE) suffer from "External Obsolescence" and have a smaller buyer pool compared to properties in low-risk zones (Zone X).
*   **Status**: COMPLETE - Integrated via FEMA NFHL ArcGIS REST API.

## 3. MLS Closed Sales (Non-Disclosure Bridge)
*   **Source**: HAR (Houston Association of Realtors) / Proprietary aggregators like Attom or CoreLogic.
*   **The Advantage**: Provides actual market transaction data in a non-disclosure state.
*   **The Argument**: Proves that actual sales are lower than HCAD's "estimated" market value using 100% accurate transaction sheets.
*   **Status**: Currently using RentCast (Estimated/AVM) as a proxy.

## 4. Nuisance & Locational Geo-Data
*   **Source**: OpenStreetMap / Harris County GIS / Google Maps API.
*   **The Advantage**: Detects negative externalities (Power lines, Tier 1 busy roads, industrial proximity).
*   **The Argument**: Adjusts value downward for "Locational Obsolescence" that isn't reflected in standard building-area-based equity comparisons.
*   **Status**: Potential for future automation via Vision Agent + GIS.

## 5. School District/Rating Deltas
*   **Source**: Texas Education Agency (TEA) / GreatSchools API.
*   **The Advantage**: Accounts for the "School Divide" within neighborhoods.
*   **The Argument**: Justifies a discount if a property is zoned to a lower-rated school compared to its equity comparables on the same street or neighborhood.
*   **Status**: Publicly available data, requires boundary mapping.
