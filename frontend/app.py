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
            # Call the real backend API
            response = requests.get(f"http://localhost:8000/protest/{account_number}")
            if response.status_code == 200:
                data = response.json()
                
                property_data = data['property']
                equity_data = data['equity']
                vision_data = data['vision']
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Appraised Value", f"${property_data['appraised_value']:,}")
                with col2:
                    st.metric("Justified Value", f"${equity_data['justified_value_floor']:,}", 
                              delta=f"-{property_data['appraised_value'] - equity_data['justified_value_floor']:,}")
                with col3:
                    potential_savings = (property_data['appraised_value'] - equity_data['justified_value_floor']) * 0.025
                    st.metric("Est. Annual Savings", f"${potential_savings:,.2f}")

                st.divider()

                # Savings Meter
                st.subheader("Savings Meter")
                st.progress(min(1.0, max(0.0, (property_data['appraised_value'] - equity_data['justified_value_floor']) / 100000)))
                
                # Equity 5 Table
                st.subheader("The 'Equity 5' Comparables")
                st.table(pd.DataFrame(equity_data['equity_5']))

                # Condition Issues Gallery
                st.subheader("Condition Issues Detected")
                if vision_data:
                    cols = st.columns(len(vision_data))
                    for idx, issue in enumerate(vision_data):
                        with cols[idx]:
                            st.warning(f"**{issue['issue']}**")
                            st.write(f"Deduction: -${issue['deduction']:,}")
                else:
                    st.write("No major exterior issues detected.")

                st.divider()
                
                # Narrative
                st.subheader("Evidence Narrative")
                st.write(data['narrative'])
                
                # Download FORM 41.44
                if os.path.exists(data['form_path']):
                    with open(data['form_path'], "rb") as f:
                        st.download_button(
                            label="Download Official Form 41.44",
                            data=f.read(),
                            file_name=f"HCAD_Protest_{account_number}.pdf",
                            mime="application/pdf"
                        )
            else:
                st.error("Failed to generate protest from backend.")

        except Exception as e:
            st.error(f"Error generating protest: {e}")

        except Exception as e:
            st.error(f"Error generating protest: {e}")
else:
    st.info("Enter an HCAD Account Number in the sidebar to begin.")
