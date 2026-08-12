"""Sidebar controls whose values map to real API parameters."""

from datetime import datetime

import streamlit as st


def symbol_selector(pairs_list):
    st.markdown("### 🎯 Select Trading Pair")
    if not pairs_list:
        st.warning("No trading pairs found. Check that both legs have tick data.")
        return None
    return st.selectbox("Choose pair:", options=pairs_list, index=0, key="pair_selector")


def timeframe_selector():
    st.markdown("### ⏰ Timeframe")
    return st.selectbox("Select timeframe:", ["1min", "5min", "15min", "1h", "4h", "1D"], index=0, key="timeframe_selector")


def regression_selector():
    st.markdown("### 🧮 Hedge Model")
    return st.selectbox(
        "Choose model:",
        ["OLS + Kalman"],
        index=0,
        key="regression_selector",
        help="The backend currently computes both static OLS and dynamic Kalman hedge ratios.",
    )


def rolling_window_slider():
    st.markdown("### 🔁 Rolling Window")
    return st.slider("Rolling window:", 20, 300, 100, 10, key="rolling_window_slider")


def adf_test_button():
    st.markdown("### 🧪 Stationarity Test")
    return st.button("Run ADF Test", key="adf_test_button")


def auto_refresh_toggle():
    st.markdown("### 🔄 Auto Refresh")
    return st.selectbox("Refresh every:", [0, 15, 30, 60, 120, 300], index=3, key="auto_refresh_toggle")


def run_analytics_button():
    st.markdown("### ▶️ Execute Analytics")
    return st.button("Run Analytics", key="run_analytics_button")


def analytics_control_panel(pairs_list):
    st.sidebar.header("⚙️ Control Panel")
    pair = symbol_selector(pairs_list)
    timeframe = timeframe_selector()
    regression = regression_selector()
    window = rolling_window_slider()
    adf_triggered = adf_test_button()
    auto_refresh = auto_refresh_toggle()
    run_clicked = run_analytics_button()
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Last UI refresh: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.sidebar.caption("Backend: Flask API")
    return {
        "symbol": pair,
        "timeframe": timeframe,
        "regression": regression,
        "window": window,
        "adf_triggered": adf_triggered,
        "auto_refresh": auto_refresh,
        "run_clicked": run_clicked,
    }
