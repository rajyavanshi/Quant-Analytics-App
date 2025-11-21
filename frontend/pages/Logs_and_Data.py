# =====================================================
# File: frontend/pages/5_Logs_and_Data.py
# Purpose: Unified data & log viewer
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
from components.api_client import get_recent_ticks, get_cleaned_analytics, get_logs
from components.data_viewer import render_dataframe_table, render_json_block, render_logs_block

st.set_page_config(page_title=" Logs & Data", layout="wide")

st.title(" Logs & Data Viewer")
st.caption("Inspect backend logs, raw tick streams, and processed analytics tables for debugging & validation.")
st.markdown("---")

# --------------------------------------------
# Tabs for Logs / Tick Data / Analytics
# --------------------------------------------
tab1, tab2, tab3 = st.tabs([" Logs", " Tick Data", " Analytics Tables"])

with tab1:
    st.subheader("Backend Logs")
    limit = st.slider("Lines to fetch", 50, 500, 200, step=50)
    if st.button("Fetch Logs"):
        res = get_logs(limit)
        if isinstance(res, dict) and res.get("status") == "success":
            render_logs_block(res["data"])
        else:
            st.warning("No log data available or API not implemented yet.")

with tab2:
    st.subheader("Recent Tick Data")
    sym = st.text_input("Symbol", "BTCUSDT", help="Enter trading symbol (e.g., BTCUSDT)")
    n = st.number_input("Limit", 10, 1000, 50, step=10)
    if st.button("Fetch Ticks"):
        res = get_recent_ticks(sym, n)
        if isinstance(res, dict) and res.get("status") == "success":
            render_dataframe_table(res["data"], key=f"ticks_{sym}")
        else:
            st.warning("No tick data found or endpoint unavailable.")

with tab3:
    st.subheader("Cleaned Analytics Data")
    sym = st.text_input("Pair Symbol", "BTCUSDT_ETHUSDT")
    limit = st.number_input("Limit Rows", 50, 5000, 200)
    if st.button("Fetch Analytics"):
        res = get_cleaned_analytics(sym, limit)
        if isinstance(res, dict) and res.get("status") == "success":
            render_dataframe_table(res["data"], key=f"analytics_{sym}")
        else:
            st.warning("No analytics data found or endpoint unavailable.")
