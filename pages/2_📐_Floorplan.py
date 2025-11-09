import os
import requests
import streamlit as st

def resolve_api_base():
    bases = []
    env_base = os.getenv("API_BASE")
    if env_base:
        bases.append(env_base)
    try:
        secret_base = st.secrets.get("API_BASE")
        if secret_base and secret_base not in bases:
            bases.append(secret_base)
    except Exception:
        pass
    bases.append("http://api:8000")
    bases.append("http://host.docker.internal:8000")
    bases.append("http://localhost:8000")
    for b in bases:
        try:
            r = requests.get(f"{b}/health", timeout=10)
            if r.ok:
                return b
        except Exception:
            continue
    return "http://api:8000"

API_BASE = resolve_api_base()
st.caption(f"Using API: {API_BASE}")

st.set_page_config(page_title="SmartEstate – Floorplan", layout="wide")
st.title("📐 Parse Floorplan")

col1, col2 = st.columns([1,1])

with col1:
    uploaded = st.file_uploader("Upload floorplan image", type=["jpg", "jpeg", "png"]) 
    if st.button("Analyze"):
        if not uploaded:
            st.warning("Please upload an image.")
        else:
            try:
                files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "image/jpeg")}
                data = {}
                resp = requests.post(f"{API_BASE}/parse_floorplan", files=files, data=data, timeout=120)
                resp.raise_for_status()
                res = resp.json()
                st.success("Parsed successfully")
                st.json({k: v for k, v in res.items() if k != "detected_texts"})
                st.caption("Detected texts (sample)")
                st.write(", ".join(res.get("detected_texts", [])[:20]))
                st.session_state["overlay_path"] = res.get("overlay_path")
            except Exception as e:
                st.error(f"Error: {e}")

with col2:
    overlay = st.session_state.get("overlay_path")
    if overlay and os.path.exists(overlay):
        st.image(overlay, caption="Detection + OCR Overlay", use_container_width=True)
    else:
        st.info("Overlay will appear here after analysis.")
