import streamlit as st
import requests
import pandas as pd
import os
from PIL import Image

st.set_page_config(page_title="Texas Equity AI", layout="wide")

# Sidebar
st.sidebar.title("Texas Equity AI")
st.sidebar.markdown("Automating property tax protests in Texas.")
account_number = st.sidebar.text_input("HCAD Account Number (13 digits)", value="1234567890123")
protest_button = st.sidebar.button("Generate Protest Packet")

# Main Content
st.title("Property Tax Protest Dashboard")

if protest_button:
    with st.spinner("Analyzing property, finding comparables, and detecting condition issues..."):
        try:
            # Call backend API (Assuming FastAPI is running on port 8000)
            # In a real app, this would be a full pipeline call
            # For MVP, we'll simulate the integration flow here
            
            # 1. Fetch Property Details
            # response = requests.get(f"http://localhost:8000/property/{account_number}")
            
            # Mocking the unified response for the dashboard
            mock_data = {
                "address": "123 Example St, Houston, TX",
                "appraised_value": 450000,
                "building_area": 2500,
                "justified_value": 415000,
                "potential_savings": 35000 * 0.025, # Assumed 2.5% tax rate
                "equity_5": [
                    {"address": "125 Example St", "value_per_sqft": 165, "building_area": 2450},
                    {"address": "118 Example St", "value_per_sqft": 162, "building_area": 2550},
                    {"address": "130 Example St", "value_per_sqft": 160, "building_area": 2400},
                    {"address": "110 Example St", "value_per_sqft": 168, "building_area": 2600},
                    {"address": "140 Example St", "value_per_sqft": 158, "building_area": 2500},
                ],
                "condition_issues": [
                    {"issue": "Roof Wear", "deduction": 5000, "confidence": 0.85},
                    {"issue": "Peeling Paint", "deduction": 3000, "confidence": 0.75}
                ],
                "narrative": "Based on Texas Tax Code §41.43 and §41.41, the subject property is over-appraised..."
            }
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Appraised Value", f"${mock_data['appraised_value']:,}")
            with col2:
                st.metric("Justified Value", f"${mock_data['justified_value']:,}", delta=f"-{mock_data['appraised_value'] - mock_data['justified_value']:,}")
            with col3:
                st.metric("Est. Annual Savings", f"${mock_data['potential_savings']:,.2f}")

            st.divider()

            # Savings Meter
            st.subheader("Savings Meter")
            st.progress(min(1.0, (mock_data['appraised_value'] - mock_data['justified_value']) / 100000))
            
            # Equity 5 Table
            st.subheader("The 'Equity 5' Comparables")
            df_comps = pd.DataFrame(mock_data['equity_5'])
            st.table(df_comps)

            # Condition Issues Gallery
            st.subheader("Condition Issues Detected")
            cols = st.columns(len(mock_data['condition_issues']))
            for idx, issue in enumerate(mock_data['condition_issues']):
                with cols[idx]:
                    st.warning(f"**{issue['issue']}**")
                    st.write(f"Deduction: -${issue['deduction']:,}")
                    st.write(f"Confidence: {issue['confidence']*100:.1f}%")

            st.divider()
            
            # Narrative
            st.subheader("Evidence Narrative")
            st.write(mock_data['narrative'])
            
            # Download PDF
            st.download_button(
                label="Download Evidence Packet (PDF)",
                data=b"PDF Content Placeholder", # In real app, fetch from PDF service
                file_name=f"Protest_{account_number}.pdf",
                mime="application/pdf"
            )

        except Exception as e:
            st.error(f"Error generating protest: {e}")
else:
    st.info("Enter an HCAD Account Number in the sidebar to begin.")
