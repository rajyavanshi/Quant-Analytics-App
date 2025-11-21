# =====================================================
# File: frontend/components/alert_notifier.py
# Purpose: Show toast notifications for new trading alerts
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
from datetime import datetime


def show_toast(message: str, level="info"):
    """Unified wrapper for Streamlit toast messages."""
    if level == "success":
        st.toast(message, icon="✅")
    elif level == "warning":
        st.toast(message, icon="⚠️")
    elif level == "error":
        st.toast(message, icon="🚨")
    else:
        st.toast(message, icon="💡")


def alert_notifier(new_alerts: list):
    """
    Compare new alerts with previous state and show pop-ups for unseen ones.
    """
    if "last_alert_ids" not in st.session_state:
        st.session_state["last_alert_ids"] = set()

    prev_ids = st.session_state["last_alert_ids"]
    new_ids = set()

    for alert in new_alerts:
        # Build unique id (timestamp + pair + signal)
        aid = f"{alert.get('timestamp')}_{alert.get('symbol_pair')}_{alert.get('signal')}"
        new_ids.add(aid)
        if aid not in prev_ids:
            sig = (alert.get("signal") or "OTHER").upper()
            pair = alert.get("symbol_pair") or alert.get("symbol") or "Unknown Pair"
            ts = alert.get("timestamp") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            if "LONG" in sig:
                show_toast(f"🟢 NEW LONG signal for {pair} @ {ts}", "success")
            elif "SHORT" in sig:
                show_toast(f"🔴 NEW SHORT signal for {pair} @ {ts}", "warning")
            elif "EXIT" in sig:
                show_toast(f"⚪ EXIT signal triggered for {pair}", "info")
            else:
                show_toast(f"⚙️ Misc alert for {pair}", "info")

    st.session_state["last_alert_ids"] = new_ids
