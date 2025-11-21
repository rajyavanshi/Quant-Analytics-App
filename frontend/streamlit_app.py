# =====================================================
# File: frontend/streamlit_app.py
# Purpose: Interactive, persistent Quant Analytics Dashboard (modular, stable)
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import os
import sys
import pandas as pd
import streamlit as st
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

# -----------------------------------------------------
# Import modular components
# -----------------------------------------------------
from components.api_client import (
    get_latest_analytics,
    get_recent_analytics,
    get_latest_alert,
    get_recent_alerts,
    get_alert_stats,
    get_symbols,
    get_recent_ticks,
    get_volume_summary,
    ping_server,
    get_system_status,
)
from components.ui_elements import analytics_control_panel
from components.price_chart import plot_price_chart
from components.spread_chart import plot_spread_zscore_chart
from utils.data_processing import process_analytics_data
from utils.chart_helpers import plot_rolling_correlation
from components.status_bar import render_status_bar
from components.alert_panel import render_alert_feed, render_alert_summary
from components.correlation_heatmap import plot_correlation_heatmap




# =====================================================
# PAGE CONFIGURATION
# =====================================================
st.set_page_config(
    page_title="Quant Analytics Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =====================================================
# LOAD CUSTOM DARK THEME
# =====================================================
css_path = os.path.join(os.path.dirname(__file__), "assets", "dark_theme.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# =====================================================
# FETCH SYMBOL LIST FOR SIDEBAR
# =====================================================
symbols_data = get_symbols()
symbols_list = []
if isinstance(symbols_data, dict) and symbols_data.get("status") == "success":
    symbols_list = symbols_data.get("data", [])
elif isinstance(symbols_data, dict) and "symbols" in symbols_data:
    symbols_list = symbols_data["symbols"]

# =====================================================
# RENDER UNIFIED SIDEBAR CONTROL PANEL
# =====================================================
controls = analytics_control_panel(symbols_list)

# =====================================================
# UI HELPERS
# =====================================================
def show_success(msg): st.success(msg, icon="✅")
def show_error(msg): st.error(msg, icon="⚠️")
def show_info(msg): st.info(msg, icon="ℹ️")

def display_table(data, key):
    """Display DataFrame with CSV download."""
    if data is None or len(data) == 0:
        show_info("No data available.")
        return
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, key=key)
    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download CSV",
        data=csv_data,
        file_name=f"{key}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key=f"download_{key}",
    )

def fetch_and_display(fetch_fn, limit=None, symbol=None, cache_key="data"):
    """Generic handler for fetching and displaying API data."""
    with st.spinner("Fetching data..."):
        try:
            if limit is not None and symbol is not None:
                res = fetch_fn(symbol, limit)
            elif limit is not None:
                res = fetch_fn(limit)
            else:
                res = fetch_fn()

            if isinstance(res, dict) and res.get("status") == "success":
                st.session_state[cache_key] = res["data"]
                show_success(f"Fetched {len(res['data']) if isinstance(res['data'], list) else 1} records successfully!")
                display_table(res["data"], key=cache_key)
            elif isinstance(res, list):
                st.session_state[cache_key] = res
                display_table(res, key=cache_key)
                show_success(f"Fetched {len(res)} records successfully!")
            else:
                show_error(res.get("message", "API Error"))
        except Exception as e:
            show_error(f"Unexpected error: {str(e)}")

# =====================================================
# MAIN PAGE SECTIONS
# =====================================================
page = st.sidebar.radio(
    "Select Section:",
    [
        "📊 Analytics Dashboard",
        "🚨 Alerts Monitor",
        "💾 Data Viewer",
        "📈 Volume Summary",
        "🧩 System Monitor",
    ],
)

# =====================================================
# SECTION 1 — ANALYTICS DASHBOARD
# =====================================================
if page == "📊 Analytics Dashboard":
    st.title("📊 Quant Analytics Dashboard")
    st.caption("Analyze price relationships, spreads, and mean-reversion signals in real time.")
    st.markdown("---")

    render_status_bar(controls['symbol'])

    st.markdown(
        f"**Selected Pair:** {controls['symbol']} | **Regression:** {controls['regression']} | **Rolling Window:** {controls['window']}"
    )

    records_to_show = st.number_input("Records to display on charts", min_value=50, max_value=5000, value=200, step=10)

    # run analytics trigger
    if controls["run_clicked"]:
        fetch_and_display(
            lambda limit: get_recent_analytics(controls["symbol"], limit=limit, window=controls["window"]),
            limit=records_to_show,
            cache_key="recent_analytics"
        )


        if "recent_analytics" in st.session_state:
            raw = st.session_state["recent_analytics"]
            try:
                df_processed = process_analytics_data(raw, window=controls["window"])
                st.session_state["processed_analytics"] = df_processed
            except Exception as e:
                show_error(f"Processing error: {e}")
                st.session_state["processed_analytics"] = pd.DataFrame()

    if controls["adf_triggered"]:
        st.warning("🧪 ADF test will be handled server-side (Phase 3 Integration).")

    # --- Chart Display ---
    if "processed_analytics" in st.session_state and not st.session_state["processed_analytics"].empty:
        df_plot = st.session_state["processed_analytics"]

        st.markdown("### 🔎 Latest Analytics Snapshot")
        st.dataframe(df_plot.tail(8), use_container_width=True)

        # Parse symbols for labeling
        symbol_x, symbol_y = "X", "Y"
        if "_" in controls["symbol"]:
            sx, sy = controls["symbol"].split("_", 1)
            symbol_x, symbol_y = sx, sy

        # Chart layout
        col1, col2 = st.columns(2)
        with col1:
            plot_price_chart(
                data=st.session_state["recent_analytics"],
                symbol_x=symbol_x,
                symbol_y=symbol_y,
                limit=records_to_show,
            )
        from components.context_blocks import price_chart_context, spread_chart_context, corr_chart_context
        price_chart_context(symbol_x, symbol_y)

        with col2:
            plot_spread_zscore_chart(
                data=st.session_state["recent_analytics"],
                symbol_x=symbol_x,
                symbol_y=symbol_y,
                window=controls["window"],
                limit=records_to_show,
            )
        spread_chart_context()

        # Rolling Correlation (now using safe helper)
        st.markdown("---")
        st.markdown("### 🔗 Rolling Correlation (X vs Y)")
        plot_rolling_correlation(
            raw_data=st.session_state["recent_analytics"],
            window=controls["window"],
            symbol_x=symbol_x,
            symbol_y=symbol_y,
        )
        corr_chart_context()
        
        # =====================================================
        # 🔥 Multi-Symbol Correlation Heatmap (Stage 6+ Enhancement)
        # =====================================================
        st.markdown("---")
        st.markdown("### 🧮 Multi-Symbol Correlation Heatmap")

        corr_method = st.selectbox(
            "Correlation Method",
            options=["pearson", "spearman", "kendall"],
            index=0,
            help="Choose the statistical method for correlation matrix calculation."
        )

        try:
            plot_correlation_heatmap(
                st.session_state["processed_analytics"],
                title=f"Correlation Matrix — {controls['symbol']}",
                method=corr_method
            )
        except Exception as e:
            show_error(f"Failed to generate correlation heatmap: {e}")



        # Summary Metrics
        st.markdown("---")
        st.markdown("### 🧾 Key Summary Metrics & Insights")
        try:
            last_row = df_plot.iloc[-1]
            hedge_ratio = last_row.get("hedge_ratio", last_row.get("beta_kalman", None))
            z_now = last_row.get("zscore", None)
            adf_p = last_row.get("adf_pvalue", last_row.get("adf_pval", None))
            rolling_corr_now = (
                df_plot["rolling_corr"].iloc[-1] if "rolling_corr" in df_plot.columns else None
            )

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Hedge Ratio", f"{float(hedge_ratio):.4f}" if hedge_ratio else "N/A")
            c2.metric("Z-score (now)", f"{float(z_now):.3f}" if z_now else "N/A")
            c3.metric("ADF p-value", f"{float(adf_p):.4f}" if adf_p else "N/A")
            c4.metric("Rolling Corr", f"{rolling_corr_now:.4f}" if rolling_corr_now else "N/A")
        except Exception:
            st.info("Insufficient columns for summary metrics (hedge_ratio, zscore, adf_pvalue).")

        from components.insight_panel import render_auto_insights

        with st.expander("💬 Insights (auto-generated)"):
            try:
                render_auto_insights(
                    zscore=z_now,
                    corr=rolling_corr_now,
                    adf_p=adf_p,
                    hedge_ratio=hedge_ratio,
                    pair=controls["symbol"]
                )
            except Exception as e:
                st.error(f"Error generating insights: {e}")


# =====================================================
# SECTION 2 — ALERTS MONITOR (Enhanced Stage 5)
# =====================================================
elif page == "🚨 Alerts Monitor":
    st.title("🚨 Alerts & Trading Signals")
    st.caption("Monitor trading alerts, signal frequency, and performance patterns.")
    st.markdown("---")

    # --- Auto Fetch ---
    with st.spinner("Fetching latest alerts..."):
        alerts_response = get_recent_alerts(limit=25)
        stats_response = get_alert_stats()

    # --- Alerts Feed ---
    if isinstance(alerts_response, dict) and alerts_response.get("status") == "success":
        alerts = alerts_response["data"]
        st.markdown("### 🧭 Latest Signals")
        render_alert_feed(alerts)
    else:
        st.error(alerts_response.get("message", "Failed to fetch alerts."))

    st.markdown("---")

    # --- Summary Metrics ---
    if isinstance(stats_response, dict) and stats_response.get("status") == "success":
        st.markdown("### 📊 Alert Summary & Distribution")
        render_alert_summary(stats_response["data"])
    else:
        st.info("No alert statistics available yet.")


# =====================================================
# SECTION 3 — DATA VIEWER
# =====================================================
elif page == "💾 Data Viewer":
    st.title("💾 Database & Tick Data Viewer")
    st.caption("Browse and verify symbol data directly from backend.")
    symbol = controls["symbol"] or "BTCUSDT"
    if st.button("📈 Fetch Recent Ticks", use_container_width=True):
        fetch_and_display(get_recent_ticks, limit=20, symbol=symbol, cache_key=f"ticks_{symbol}")
    for key in [k for k in st.session_state.keys() if k.startswith("ticks_")]:
        st.markdown(f"#### 📊 Recent Ticks for {key.split('_')[1]}")
        display_table(st.session_state[key], key=f"{key}_display")

# =====================================================
# SECTION 4 — VOLUME SUMMARY
# =====================================================
elif page == "📈 Volume Summary":
    st.title("📈 Volume Summary by Symbol")
    fetch_and_display(get_volume_summary, cache_key="volume_summary")

# =====================================================
# SECTION 5 — SYSTEM MONITOR
# =====================================================
elif page == "🧩 System Monitor":
    st.title("🧩 System Monitor & API Diagnostics")
    st.caption("Monitor Flask backend connectivity and server uptime.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔍 Ping Flask API", use_container_width=True):
            res = ping_server()
            if res.get("status") == "success":
                show_success("Flask backend is online ✅")
                st.json(res["data"])
            else:
                show_error(res.get("message", "Ping failed."))
    with col2:
        if st.button("📡 Get System Status", use_container_width=True):
            res = get_system_status()
            if res.get("status") == "success":
                show_success("System status retrieved successfully.")
                st.json(res["data"])
            else:
                show_error(res.get("message", "Failed to fetch system status."))

    st.caption("💡 Keep Flask server running before launching Streamlit.")
