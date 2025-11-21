# =====================================================
# File: frontend/components/ui_elements.py
# Purpose: Centralized interactive sidebar widgets for user controls
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
from datetime import datetime

# -----------------------------------------------------
# 1️⃣ SYMBOL SELECTOR
# -----------------------------------------------------
def symbol_selector(symbols_list):
    """
    Dropdown menu for symbol/pair selection.
    Args:
        symbols_list (list): List of available trading pairs.
    Returns:
        str: Selected symbol.
    """
    st.markdown("### 🎯 Select Trading Pair")
    if not symbols_list:
        st.warning("No symbols found. Please check database or API connection.")
        return None
    return st.selectbox("Choose Pair:", options=symbols_list, index=0, key="symbol_selector")


# -----------------------------------------------------
# 2️⃣ TIMEFRAME SELECTOR
# -----------------------------------------------------
def timeframe_selector():
    """
    Timeframe selection radio buttons.
    Returns:
        str: Selected timeframe (e.g., '1m', '15m', '1h').
    """
    st.markdown("### ⏰ Timeframe")
    return st.radio(
        "Select timeframe:",
        options=["1m", "5m", "15m", "1h", "4h", "1d"],
        horizontal=True,
        key="timeframe_selector"
    )


# -----------------------------------------------------
# 3️⃣ REGRESSION TYPE SELECTOR
# -----------------------------------------------------
def regression_selector():
    """
    Dropdown for regression type.
    Returns:
        str: Regression algorithm selected by user.
    """
    st.markdown("### 🧮 Regression Type")
    return st.selectbox(
        "Choose regression model:",
        options=["OLS", "Kalman", "Huber", "Theil–Sen"],
        index=0,
        key="regression_selector"
    )


# -----------------------------------------------------
# 4️⃣ ROLLING WINDOW SLIDER
# -----------------------------------------------------
def rolling_window_slider():
    """
    Slider for selecting rolling window size.
    Returns:
        int: Selected rolling window.
    """
    st.markdown("### 🔁 Rolling Window")
    return st.slider(
        "Select rolling window size:",
        min_value=20,
        max_value=300,
        value=100,
        step=10,
        key="rolling_window_slider"
    )


# -----------------------------------------------------
# 5️⃣ ADF TEST BUTTON
# -----------------------------------------------------
def adf_test_button():
    """
    Button to trigger stationarity (ADF) test.
    Returns:
        bool: True if clicked, else False.
    """
    st.markdown("### 🧪 Stationarity Test")
    return st.button("Run ADF Test", key="adf_test_button")


# -----------------------------------------------------
# 6️⃣ AUTO REFRESH TOGGLE
# -----------------------------------------------------
def auto_refresh_toggle():
    """
    Dropdown to set auto-refresh interval.
    Returns:
        int: Refresh interval in seconds.
    """
    st.markdown("### 🔄 Auto Refresh Interval (seconds)")
    return st.selectbox(
        "Auto-refresh every:",
        options=[0, 15, 30, 60, 120, 300],
        index=3,
        key="auto_refresh_toggle"
    )


# -----------------------------------------------------
# 7️⃣ RUN ANALYTICS BUTTON
# -----------------------------------------------------
def run_analytics_button():
    """
    Main button to trigger analytics fetch.
    Returns:
        bool: True if user clicked 'Run Analytics'.
    """
    st.markdown("### ▶️ Execute Analytics")
    return st.button("Run Analytics", key="run_analytics_button")


# -----------------------------------------------------
# 8️⃣ COMBINED CONTROL PANEL WRAPPER
# -----------------------------------------------------
def analytics_control_panel(symbols_list):
    """
    Renders all sidebar controls in a single unified layout
    and returns their states as a dictionary.

    Args:
        symbols_list (list): List of trading pairs fetched from backend.

    Returns:
        dict: Current user selections.
    """
    st.sidebar.header("⚙️ Control Panel")

    symbol = symbol_selector(symbols_list)
    timeframe = timeframe_selector()
    regression = regression_selector()
    window = rolling_window_slider()
    adf_triggered = adf_test_button()
    auto_refresh = auto_refresh_toggle()
    run_clicked = run_analytics_button()

    st.sidebar.markdown("---")
    st.sidebar.caption(
        f"🕓 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    st.sidebar.caption("🌐 Backend: Connected to Flask API")
    st.sidebar.markdown("---")
    st.sidebar.caption("Built with ❤️ by Suraj Prakash")

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "regression": regression,
        "window": window,
        "adf_triggered": adf_triggered,
        "auto_refresh": auto_refresh,
        "run_clicked": run_clicked
    }
