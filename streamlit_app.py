import os
import streamlit as st

st.set_page_config(page_title="SmartEstate – Home", layout="wide")

st.title("SmartEstate – Home")
st.write("Use the sidebar to navigate:")
st.markdown("- 📥 Ingest page to upload property Excel and trigger ETL")
st.markdown("- 📐 Floorplan page to parse a single image and preview overlay")
st.markdown("- 💬 Chat page to interact with the multi-agent assistant")
