import os
import requests
import streamlit as st

def resolve_api_base():
    bases = []
    env_base = os.getenv("API_BASE")
    if env_base:
        bases.append(env_base)
    # Try secrets if available
    try:
        secret_base = st.secrets.get("API_BASE")
        if secret_base and secret_base not in bases:
            bases.append(secret_base)
    except Exception:
        pass
    # Try api:8000 first (same Docker network)
    bases.append("http://api:8000")
    # Docker host fallback for Windows/macOS
    bases.append("http://host.docker.internal:8000")
    # Local dev fallback
    bases.append("http://localhost:8000")

    # Try each base and return first working one
    for b in bases:
        try:
            r = requests.get(f"{b}/health", timeout=10)
            if r.ok:
                return b
        except Exception:
            continue

    # Default to api:8000 if all fail
    return "http://api:8000"

API_BASE = resolve_api_base()
st.caption(f"Using API: {API_BASE}")

st.set_page_config(page_title="SmartEstate – Ingest", layout="centered")
st.title("📥 Ingest Properties Excel")

uploaded = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"]) 

if st.button("Ingest"):
    if not uploaded:
        st.warning("Please upload an Excel file.")
    else:
        try:
            files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            resp = requests.post(f"{API_BASE}/ingest", files=files, timeout=300)
            resp.raise_for_status()
            st.success("Ingestion complete")
            st.json(resp.json())
        except Exception as e:
            st.error(f"Error: {e}")
