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

st.set_page_config(page_title="SmartEstate – Chat", layout="centered")
st.title("💬 SmartEstate Chat")

user_id = st.text_input("User ID", value=st.session_state.get("user_id", "demo-user"))
st.session_state["user_id"] = user_id

if "history" not in st.session_state:
    st.session_state["history"] = []

prompt = st.text_input("Ask about properties", "Find 2BHK in Hyderabad under 70L")

col1, col2 = st.columns(2)
with col1:
    if st.button("Send"):
        try:
            r = requests.post(f"{API_BASE}/chat", params={"message": prompt, "user_id": user_id}, timeout=120)
            r.raise_for_status()
            data = r.json()
            st.session_state["history"].append(("user", prompt))
            st.session_state["history"].append(("assistant", data.get("result", {}).get("text", "")))
        except Exception as e:
            st.error(f"Error: {e}")

with col2:
    if st.button("Generate Report"):
        try:
            r = requests.post(f"{API_BASE}/report", data={"summary_hint": "Generate property summary"}, timeout=120)
            r.raise_for_status()
            result = r.json()
            pdf_path = result.get("pdf_path")
            if pdf_path:
                st.success(f"✅ Report generated successfully!")
                st.info(f"📄 Saved to: `{pdf_path}`")
                st.caption("The PDF is saved in the outputs/ folder on the server")
            else:
                st.warning("Report generated but no PDF path returned")
        except Exception as e:
            st.error(f"Error: {e}")

st.divider()
for role, text in st.session_state["history"][-10:]:
    st.markdown(f"**{role.capitalize()}:** {text}")
