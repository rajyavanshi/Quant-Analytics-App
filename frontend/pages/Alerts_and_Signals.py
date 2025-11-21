# =====================================================
# File: frontend/pages/2_ _Alerts_and_Signals.py
# Purpose: Real-time alerts monitor with filters, auto-refresh (non-blocking), pagination & toast notifier
# Author: Suraj Prakash (Quant Developer) - UPDATED
# =====================================================

import streamlit as st
from datetime import datetime
import math

from components.api_client import get_recent_alerts, get_alert_stats
from components.alert_panel import render_alert_feed, render_alert_summary
from components.alert_notifier import alert_notifier   #  NEW: Toast system

# -----------------------------------------------------
# Page Configuration
# -----------------------------------------------------
st.set_page_config(page_title=" Alerts & Signals", layout="wide")

# -----------------------------------------------------
# Header & Intro
# -----------------------------------------------------
st.title(" Alerts & Trading Signals")
st.caption("Monitor trading alerts, signal frequency, and performance patterns in real-time.")
st.markdown("---")

# -----------------------------------------------------
# Control Panel (Filters + Pagination + Refresh)
# -----------------------------------------------------
col1, col2, col3, col4 = st.columns([1.2, 1, 1, 1])

with col1:
    signal_filter = st.selectbox(
        " Filter by Signal Type",
        options=["All", "LONG", "SHORT", "EXIT", "OTHER"],
        index=0
    )

with col2:
    limit = st.slider("Alert fetch limit (most recent)", 10, 500, 100, step=10,
                      help="How many most recent alerts to fetch from backend")

with col3:
    page_size = st.selectbox("Page size", options=[5, 10, 20, 50], index=1)

with col4:
    refresh_interval = st.selectbox(
        "Auto Refresh Interval",
        options=["Off", 15, 30, 60],
        index=2,
        help="Use auto-refresh for live updates. Requires `streamlit-autorefresh` package for non-blocking refresh."
    )

st.markdown("---")

# -----------------------------------------------------
# Non-blocking Auto-refresh (preferred: st_autorefresh)
# -----------------------------------------------------
use_autorefresh = False
autorefresh_count = None

try:
    from streamlit_autorefresh import st_autorefresh
    if refresh_interval != "Off":
        autorefresh_count = st_autorefresh(
            interval=int(refresh_interval) * 1000, key="alerts_autorefresh"
        )
        use_autorefresh = True
except Exception:
    use_autorefresh = False

# Manual refresh fallback
if not use_autorefresh:
    refresh_col1, refresh_col2 = st.columns([1, 1])
    with refresh_col1:
        if st.button(" Refresh now", use_container_width=True):
            st.session_state["manual_alerts_refresh"] = datetime.utcnow().isoformat()
    with refresh_col2:
        if refresh_interval != "Off":
            st.info(
                f"Auto-refresh requires `streamlit-autorefresh` package. Current selection: {refresh_interval}s (install recommended)."
            )
        else:
            st.caption("Auto-refresh disabled.")

# -----------------------------------------------------
# Fetch Alerts + Stats (safe)
# -----------------------------------------------------
with st.spinner("Fetching latest alerts..."):
    try:
        alerts_response = get_recent_alerts(limit=limit)
    except Exception as e:
        alerts_response = {"status": "error", "message": str(e), "data": []}

with st.spinner("Fetching alert stats..."):
    try:
        stats_response = get_alert_stats()
    except Exception as e:
        stats_response = {"status": "error", "message": str(e), "data": {}}

# -----------------------------------------------------
# Normalize & Filter alerts list
# -----------------------------------------------------
alerts_data = []
if isinstance(alerts_response, dict) and alerts_response.get("status") == "success":
    alerts_data = alerts_response.get("data", []) or []
elif isinstance(alerts_response, list):
    alerts_data = alerts_response
else:
    alerts_data = alerts_response.get("data", []) if isinstance(alerts_response, dict) else []

# Filter by signal type
if signal_filter != "All" and alerts_data:
    fl = signal_filter.lower()
    alerts_data = [a for a in alerts_data if fl in (str(a.get("signal", "")).lower())]

# -----------------------------------------------------
#   Live Toast Notifier Integration
# -----------------------------------------------------
if alerts_data:
    try:
        alert_notifier(alerts_data)
    except Exception as e:
        st.warning(f"Notifier error: {e}")

# -----------------------------------------------------
# Pagination
# -----------------------------------------------------
total_alerts = len(alerts_data)
if total_alerts == 0:
    st.warning("No alerts found for the current selection / filter.")
else:
    total_pages = math.ceil(total_alerts / page_size)
    if "alerts_page" not in st.session_state:
        st.session_state["alerts_page"] = 1

    # Navigation controls
    pcol1, pcol2, pcol3, pcol4 = st.columns([1, 1, 1, 2])
    with pcol1:
        if st.button(" First", key="first_page"):
            st.session_state["alerts_page"] = 1
    with pcol2:
        if st.button(" Prev", key="prev_page"):
            st.session_state["alerts_page"] = max(1, st.session_state["alerts_page"] - 1)
    with pcol3:
        if st.button("Next ", key="next_page"):
            st.session_state["alerts_page"] = min(total_pages, st.session_state["alerts_page"] + 1)
    with pcol4:
        page_input = st.number_input("Page", min_value=1, max_value=total_pages,
                                     value=st.session_state["alerts_page"], step=1)
        if page_input != st.session_state["alerts_page"]:
            st.session_state["alerts_page"] = int(page_input)

    # Slice data
    start_idx = (st.session_state["alerts_page"] - 1) * page_size
    end_idx = start_idx + page_size
    alerts_sorted = sorted(alerts_data, key=lambda x: x.get("timestamp", ""), reverse=True)
    page_alerts = alerts_sorted[start_idx:end_idx]

    st.markdown(
        f"###  Showing alerts {start_idx + 1}–{min(end_idx, total_alerts)} "
        f"of {total_alerts} (Page {st.session_state['alerts_page']} / {total_pages})"
    )
    render_alert_feed(page_alerts)

# -----------------------------------------------------
# Summary Section
# -----------------------------------------------------
st.markdown("---")
if isinstance(stats_response, dict) and stats_response.get("status") == "success":
    st.markdown("###  Alert Summary & Distribution")
    render_alert_summary(stats_response.get("data", {}))
else:
    st.info("No alert statistics available yet or failed to fetch them.")

# -----------------------------------------------------
# Developer / Debug Info
# -----------------------------------------------------
with st.expander(" Debug: Last raw response"):
    st.write("alerts_response:", alerts_response)
    st.write("stats_response:", stats_response)
    st.write({
        k: v
        for k, v in st.session_state.items()
        if k.startswith("alerts") or k in ["manual_alerts_refresh", "alerts_page"]
    })
