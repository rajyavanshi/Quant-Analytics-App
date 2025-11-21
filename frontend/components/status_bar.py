# =====================================================
# File: frontend/components/status_bar.py
# Purpose: Display live server status, active pair, and last refresh timestamp
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
from datetime import datetime
from components.api_client import ping_server

def render_status_bar(active_pair: str):
    """Renders a top status bar showing server status and current analytics pair."""
    ping = ping_server()
    server_ok = ping.get("status") == "success"
    server_time = ping.get("data", {}).get("server_time", "N/A")

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.metric(label="🖥️ Server Status", value="🟢 Online" if server_ok else "🔴 Offline")
    with c2:
        st.metric(label="🕒 Server Time", value=server_time)
    with c3:
        st.metric(label="📊 Active Pair", value=active_pair or "Not Selected")

    st.markdown("---")
