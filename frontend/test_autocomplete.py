import streamlit as st
import requests
from st_keyup import st_keyup

st.title("Address Autocomplete Test")

API_KEY = "YOUR_GEOAPIFY_KEY" # We will use a demo key or let user provide one, but for now just testing the UI flow

value = st_keyup("Enter Address", key="address_input")

if value:
    st.write(f"Searching for: {value}")
    # In a real app we would call:
    # url = f"https://api.geoapify.com/v1/geocode/autocomplete?text={value}&apiKey={API_KEY}"
    # But for testing UI, we just mock it:
    mock_results = [
        f"{value} Main St, Houston, TX",
        f"{value} Oak Ave, Dallas, TX",
        f"123 {value} Blvd, Austin, TX"
    ]
    
    selected = st.selectbox("Suggestions", [""] + mock_results, key="suggestion_box")
    if selected:
        st.success(f"Selected: {selected}")
