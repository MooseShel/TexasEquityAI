
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

# Main Content
st.title("Property Tax Protest Dashboard")

# Input Section - Supports Account Number OR Address
account_number = st.text_input("Enter HCAD Account Number or Street Address", 
                              placeholder="e.g. 0660460360030 or 935 Lamonte Ln")

def get_protest_data(account_input):
    params = {
        "manual_address": m_address if m_address else None,
        "manual_value": m_value if m_value > 0 else None,
        "manual_area": m_area if m_area > 0 else None
    }
    # backend.main handles address resolution automatically
    try:
        response = requests.get(f"http://localhost:8000/protest/{account_input}", params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return {"detail": f"Backend Error: {response.status_code} - {response.text}"}
    except Exception as e:
        return {"detail": f"Connection Error: {str(e)}"}

if st.button("🚀 Generate Protest Packet", type="primary"):
    if not account_number:
        st.error("Please enter an account number or address.")
    else:
        with st.spinner("🔍 Analysis in progress... Resolving address, pulling market data, and generating evidence (this may take 30-60s)"):
            data = get_protest_data(account_number)
            
            if "detail" in data:
                st.error(f"Error: {data['detail']}")
            else:
                # Layout: Tabs for organized view
                tab1, tab2, tab3, tab4 = st.tabs(["🏠 Property & Market", "⚖️ Equity Analysis", "📸 Vision Analysis", "📄 Official Protest"])
                
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
                    st.metric("Justified Value (Equity)", f"${justified_val:,.0f}", 
                              delta=f"-${data['property'].get('appraised_value', 0) - justified_val:,.0f} Savings",
                              delta_color="normal")
                    
                    st.markdown("### The 'Equity 5' Comparables")
                    df = pd.DataFrame(data['equity']['equity_5'])
                    
                    # Currency Formatting for Table
                    st.dataframe(
                        df,
                        column_config={
                            "address": "Address",
                            "appraised_value": st.column_config.NumberColumn("Appraised Value", format="$%d"),
                            "building_area": st.column_config.NumberColumn("Sq Ft", format="%d sqft"),
                            "value_per_sqft": st.column_config.NumberColumn("Value/SqFt", format="$%.2f"),
                            "similarity_score": st.column_config.NumberColumn("Similarity", format="%.2f")
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                
                # TAB 3: Vision Analysis
                with tab3:
                    st.subheader("Condition Issues Detected")
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
