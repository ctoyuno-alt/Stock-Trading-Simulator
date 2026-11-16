"""
Streamlit Dashboard Entrypoint for Gemini AI Paper Trading Simulator (NSE/BSE).
Placeholder scaffold for Phase 2 - will be fully populated in Phase 8.
"""

import streamlit as st

st.set_page_config(
    page_title="AI Paper Trading Simulator (NSE/BSE)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 Gemini-Powered AI Paper Trading Simulator")
st.caption("National Stock Exchange (NSE) & Bombay Stock Exchange (BSE) Virtual Trading Platform")

st.info(
    "System Initializing. Backend API and PostgreSQL database services are active. "
    "Full dashboard visual suite will be linked in upcoming phases."
)

st.markdown("""
### Core Guardrails Active:
- **Capital**: ₹100,000.00 INR (Virtual)
- **Mode**: Paper Trading Only (No Real Broker Integration)
- **Market Hours**: 09:15 to 15:30 IST (Asia/Kolkata)
- **Risk Limit**: 1.0% Equity Risk Per Position with Mandatory Stop-Loss
""")
