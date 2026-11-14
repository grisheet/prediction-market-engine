import os

import httpx
import streamlit as st

st.set_page_config(page_title="Prediction-market research", layout="wide")
st.title("Prediction-market research")
st.warning("SYNTHETIC OFFLINE DEMO | Live disabled | Eligibility unverified | Never armed")
st.caption("Fixed fixtures demonstrate pricing. Times and prices do not represent live markets.")
base = os.environ.get("PM_API_URL", "http://127.0.0.1:8000")
try:
    with httpx.Client(base_url=base, timeout=5) as client:
        for title, path in (
            ("Readiness and risk", "/risk"),
            ("Markets", "/markets"),
            ("Books", "/books"),
            ("Opportunities", "/opportunities"),
            ("Orders and runs", "/orders"),
            ("Positions", "/positions"),
            ("Reports", "/reports"),
        ):
            st.subheader(title)
            response = client.get(path)
            response.raise_for_status()
            st.json(response.json())
        token = os.environ.get("PM_CONTROL_TOKEN", "")
        if st.button("Run synthetic paper simulation", disabled=not bool(token)):
            result = client.post(
                "/controls/paper/start", headers={"Authorization": "Bearer " + token}
            )
            st.json(result.json())
        if st.button("Activate persistent kill switch", disabled=not bool(token)):
            result = client.post("/controls/kill", headers={"Authorization": "Bearer " + token})
            st.json(result.json())
except httpx.HTTPError:
    st.error("Local API unavailable. Start it with: uv run pm-engine api")
