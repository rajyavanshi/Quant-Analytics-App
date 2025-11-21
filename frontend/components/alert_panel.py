# =====================================================
# File: frontend/components/alert_panel.py
# Purpose: Real-time trading alert visualization and stats panel
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime


# -----------------------------------------------------
# 1️⃣ — Helper: Map signal → label + color
# -----------------------------------------------------
def get_signal_style(signal: str):
    s = (signal or "").upper().strip()

    if "LONG" in s:
        return ("🟢 LONG", "#00C853")
    elif "SHORT" in s:
        return ("🔴 SHORT", "#FF5252")
    elif "EXIT" in s or "CLOSE" in s:
        return ("⚪ EXIT", "#B0BEC5")
    elif "NEUTRAL" in s or "NONE" in s or "NO" in s or s == "":
        return ("🟡 NEUTRAL", "#FFD54F")
    else:
        # fallback for unexpected/unclassified signals
        return ("⚙️ UNKNOWN", "#FFA726")


# -----------------------------------------------------
# 2️⃣ — Render single alert card
# -----------------------------------------------------
def render_alert_card(alert: dict):
    """Displays a single alert entry as a styled container."""
    signal_label, color = get_signal_style(alert.get("signal", ""))
    pair = alert.get("symbol_pair") or alert.get("symbol") or "Unknown Pair"
    ts = alert.get("timestamp", "")
    reason = alert.get("reason", "") or alert.get("context", "No reason provided")

    # Infer NEUTRAL state from message content
    if "neutral" in reason.lower() or "no trade" in reason.lower():
        signal_label, color = ("🟡 NEUTRAL", "#FFD54F")

    html = f"""
    <div style="
        background-color:#141821;
        border-left:4px solid {color};
        border-radius:10px;
        padding:0.8rem 1rem;
        margin-bottom:0.6rem;
        line-height:1.4;
        color:#E0E0E0;
        font-size:0.9rem;">
        <b style="color:{color}">{signal_label}</b> &nbsp; <b>{pair}</b><br>
        <span style="font-size:0.8rem;color:#9E9E9E;">{ts}</span><br>
        <i>{reason}</i>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# -----------------------------------------------------
# 3️⃣ — Summary Bar
# -----------------------------------------------------
def render_alert_summary(stats: dict):
    """Display aggregated stats of alert signals."""
    st.markdown("### 📊 Alert Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("🟢 LONG", stats.get("LONG", 0))
    col2.metric("🔴 SHORT", stats.get("SHORT", 0))
    col3.metric("📈 TOTAL", stats.get("TOTAL", 0))

    # Optional pie visualization
    if sum(stats.values()) > 0:
        df = pd.DataFrame([
            {"Signal": k, "Count": v}
            for k, v in stats.items() if k != "TOTAL"
        ])
        fig = px.pie(
            df,
            names="Signal",
            values="Count",
            color="Signal",
            color_discrete_map={
                "LONG": "#00C853",
                "SHORT": "#FF5252",
                "EXIT": "#B0BEC5",
                "NEUTRAL": "#FFD54F"
            },
            hole=0.4
        )
        fig.update_layout(
            paper_bgcolor="#0E1117",
            font=dict(color="#FAFAFA"),
            margin=dict(l=20, r=20, t=10, b=10),
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------------------
# 4️⃣ — Render Alert Feed
# -----------------------------------------------------
def render_alert_feed(alerts: list):
    """Displays a list of alerts in reverse chronological order."""
    if not alerts:
        st.info("No alerts found.")
        return

    alerts_sorted = sorted(alerts, key=lambda x: x.get("timestamp", ""), reverse=True)
    for alert in alerts_sorted:
        render_alert_card(alert)
