
import streamlit as st
import requests
import pandas as pd
import os
from PIL import Image

st.set_page_config(page_title="Texas Equity AI", layout="wide")

# Custom CSS for polished look
# Removed .stMetric background to fix contrast issues in Dark Mode
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.title("Texas Equity AI 🤠")
st.sidebar.markdown("Automating property tax protests in Harris County.")

with st.sidebar.expander("Manual Data (Optional Override)"):
    m_address = st.text_input("Property Address")
    m_value = st.number_input("Appraised Value", value=0)
    m_area = st.number_input("Building Area (sqft)", value=0)

st.sidebar.divider()
st.sidebar.subheader("📈 Savings Calculator")
tax_rate = st.sidebar.slider("Property Tax Rate (%)", 1.0, 4.0, 2.5, 0.1)
st.sidebar.info(f"Standard Harris County rate is ~2.5%")

# Main Content
st.title("Property Tax Protest Dashboard")

# Input Section - Supports Account Number OR Address
account_number = st.text_input("Enter HCAD Account Number or Street Address", 
                              placeholder="e.g. 0660460360030 or 935 Lamonte Ln")

import json

def get_protest_stream(account_input):
    params = {
        "manual_address": m_address if m_address else None,
        "manual_value": m_value if m_value > 0 else None,
        "manual_area": m_area if m_area > 0 else None
    }
    try:
        # Use stream=True to read status updates as they come
        return requests.get(f"http://localhost:8000/protest/{account_input}", params=params, stream=True)
    except Exception as e:
        return None

if st.button("🚀 Generate Protest Packet", type="primary"):
    if not account_number:
        st.error("Please enter an account number or address.")
    else:
        # User-friendly multi-step progress tracking
        with st.status("🏗️ Building your Protest Packet...", expanded=True) as status:
            response = get_protest_stream(account_number)
            
            if not response:
                status.update(label="❌ Connection Failed", state="error", expanded=True)
                st.error("Could not connect to the analysis engine. Please ensure the backend is running.")
            else:
                final_data = None
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line.decode('utf-8'))
                        
                        if "status" in chunk:
                            st.write(chunk["status"])
                        
                        if "error" in chunk:
                            status.update(label="❌ Generation Failed", state="error", expanded=True)
                            st.error(f"### 🌩️ Something went wrong\n{chunk['error']}")
                            st.info("💡 **Pro-tip**: Try entering the numeric HCAD Account Number directly if Address lookup fails.")
                            break
                            
                        if "data" in chunk:
                            final_data = chunk["data"]
                
                if final_data:
                    status.update(label="✅ Protest Packet Ready!", state="complete", expanded=False)
                    
                    # Layout: Tabs for organized view
                    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 Property & Market", "⚖️ Equity Analysis", "📸 Vision Analysis", "📄 Official Protest", "⚙️ Advanced Data"])
                    
                    # Store data for use in tabs
                    data = final_data
                
                # TAB 1: Property & Market
                with tab1:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Property Details")
                        st.json(data['property'])
                        
                    with col2:
                        st.subheader("Market Analysis")
                        appraised = data['property'].get('appraised_value', 0)
                        market = data['market_value']
                        
                        st.metric("Appraised Value", f"${appraised:,.0f}")
                        
                        delta_val = market - appraised
                        st.metric("Market Value (RentCast)", f"${market:,.0f}", 
                                 delta=f"${delta_val:,.0f}",
                                 delta_color="inverse")
                
                # TAB 2: Equity Analysis
                with tab2:
                    st.subheader("Equity Fairness Analysis")
                    justified_val = data['equity']['justified_value_floor']
                    savings_value = appraised - justified_val
                    est_tax_savings = (savings_value * (tax_rate / 100))
                    
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        st.metric("Justified Value (Equity)", f"${justified_val:,.0f}", 
                                  delta=f"-${savings_value:,.0f} Reduction",
                                  delta_color="normal")
                    with ec2:
                        st.metric("💰 Estimated Tax Savings", f"${est_tax_savings:,.0f}", 
                                  help=f"Based on a {tax_rate}% tax rate. Savings = Reductions x Rate.")

                    st.markdown("### The 'Equity 5' Comparables")
                    df = pd.DataFrame(data['equity']['equity_5'])
                    
                    # Currency Formatting for Table
                    st.dataframe(
                        df,
                        column_config={
                            "address": "Address",
                            "appraised_value": st.column_config.NumberColumn("Appraised Value", format="$%,d"),
                            "building_area": st.column_config.NumberColumn("Sq Ft", format="%,d sqft"),
                            "value_per_sqft": st.column_config.NumberColumn("Value/SqFt", format="$%,.2f"),
                            "similarity_score": st.column_config.NumberColumn("Similarity", format="%.2f")
                        },
                        width="stretch", 
                        hide_index=True
                    )
                
                with tab3:
                    st.subheader("Condition Issues Detected")
                    
                    # Display Vision Image
                    evidence_img = data.get('evidence_image_path')
                    if evidence_img and os.path.exists(evidence_img):
                        st.image(evidence_img, caption="Vision Agent Analysis Source", width=600)
                    elif evidence_img:
                        st.warning(f"Image processed but file unavailable: {evidence_img}")
                    
                    st.divider()
                    vision_data = data.get('vision', [])
                    if vision_data:
                        cols = st.columns(len(vision_data))
                        for idx, issue in enumerate(vision_data):
                            # Handle case where cols might be fewer than issues if len is large
                            if idx < len(cols):
                                with cols[idx]:
                                    st.warning(f"**{issue['issue']}**")
                                    st.write(f"Deduction: -${issue['deduction']:,}")
                    else:
                        st.success("No major exterior issues detected.")

                # TAB 4: Narrative & PDF
                with tab4:
                    st.subheader("Evidence Narrative")
                    st.info(data['narrative'])
                    
                    st.divider()
                    
                    form_path = data.get('form_path')
                    if form_path and os.path.exists(form_path):
                        with open(form_path, "rb") as f:
                            st.download_button(
                                label="⬇️ Download Official Form 41.44 (PDF)",
                                data=f.read(),
                                file_name=f"HCAD_Protest_{data['property'].get('account_number')}.pdf",
                                mime="application/pdf",
                                type="primary"
                            )
                    else:
                        st.warning("PDF generation pending or failed.")

                # TAB 5: Advanced / Debug
                with tab5:
                    st.subheader("Raw Scraper & API Data")
                    st.write("This tab displays the underlying data used for calculations.")
                    
                    with st.expander("HCAD Raw Details", expanded=False):
                        st.json(data['property'])
                    
                    with st.expander("Equity Engine Comps", expanded=False):
                        st.json(data['equity'])
                    
                    with st.expander("RentCast Market Data", expanded=False):
                        st.write(f"Final Market Value: ${data['market_value']:,.0f}")
                        if 'rentcast_data' in data['property']:
                            st.json(data['property']['rentcast_data'])
                        else:
                            st.info("No direct RentCast payload available (using fallback/cached value).")
